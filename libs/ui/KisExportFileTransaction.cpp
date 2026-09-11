/* SPDX-FileCopyrightText: 2026 Trieflow LLC
 * SPDX-License-Identifier: GPL-3.0-or-later */
#include "KisExportFileTransaction.h"
#include <QCryptographicHash>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QTemporaryDir>
#include <cerrno>
#include <cstdio>
#include <fcntl.h>
#ifdef Q_OS_WIN
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <io.h>
#else
#include <sys/stat.h>
#include <unistd.h>
#ifdef Q_OS_LINUX
#include <sys/syscall.h>
#endif
#endif
namespace {
[[noreturn]] void fail(const QString &message) { throw std::runtime_error(message.toUtf8().constData()); }
struct Stamp {
    KisExportFileIdentity identity;
    quint64 modified=0, changed=0;
    bool operator==(const Stamp &s) const { return identity==s.identity && modified==s.modified && changed==s.changed; }
};
Stamp stamp(QFile &file)
{
#ifdef Q_OS_WIN
    BY_HANDLE_FILE_INFORMATION info{};
    const auto handle=reinterpret_cast<HANDLE>(_get_osfhandle(int(file.handle())));
    if (!GetFileInformationByHandle(handle,&info) || (info.dwFileAttributes & (FILE_ATTRIBUTE_DIRECTORY|FILE_ATTRIBUTE_REPARSE_POINT))) fail("Cannot inspect regular export file: "+file.fileName());
    FILE_BASIC_INFO basic{};
    if (!GetFileInformationByHandleEx(handle,FileBasicInfo,&basic,sizeof(basic))) fail("Cannot inspect export modification identity.");
    return {{info.dwVolumeSerialNumber,(quint64(info.nFileIndexHigh)<<32)|info.nFileIndexLow,
        (quint64(info.nFileSizeHigh)<<32)|info.nFileSizeLow,{}},quint64(basic.LastWriteTime.QuadPart),quint64(basic.ChangeTime.QuadPart)};
#else
    struct stat info{};
    if (fstat(int(file.handle()),&info)!=0 || !S_ISREG(info.st_mode)) fail("Cannot inspect regular export file: "+file.fileName());
#ifdef Q_OS_MACOS
    const auto modified=info.st_mtimespec, changed=info.st_ctimespec;
#else
    const auto modified=info.st_mtim, changed=info.st_ctim;
#endif
    return {{quint64(info.st_dev),quint64(info.st_ino),quint64(info.st_size),{}},
        quint64(modified.tv_sec)*1000000000+quint64(modified.tv_nsec),
        quint64(changed.tv_sec)*1000000000+quint64(changed.tv_nsec)};
#endif
}
void openRegular(QFile &file)
{
    const auto path=file.fileName();
    const QFileInfo info(path);
    if (!info.isFile() || info.isSymLink()) fail("Export path must be a regular file: "+path);
#ifdef Q_OS_WIN
    HANDLE handle=CreateFileW(reinterpret_cast<LPCWSTR>(path.utf16()),GENERIC_READ,
        FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,nullptr,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT,nullptr);
    if (handle==INVALID_HANDLE_VALUE) fail("Cannot open export file: "+path);
    const int fd=_open_osfhandle(reinterpret_cast<intptr_t>(handle),_O_RDONLY|_O_BINARY);
    if (fd<0) { CloseHandle(handle); fail("Cannot read export file: "+path); }
#else
    const int fd=::open(QFile::encodeName(path).constData(),O_RDONLY|O_NOFOLLOW|O_NONBLOCK);
    if (fd<0) fail("Cannot open export file: "+path);
#endif
    if (!file.open(fd,QIODevice::ReadOnly,QFileDevice::AutoCloseHandle)) {
#ifdef Q_OS_WIN
        _close(fd);
#else
        ::close(fd);
#endif
        fail("Cannot read export file: "+path);
    }
    stamp(file);
}
KisExportFileIdentity inspect(const QString &path)
{
    QFile file(path); openRegular(file); const auto before=stamp(file);
    QCryptographicHash hash(QCryptographicHash::Sha256);
    while (!file.atEnd()) {
        const auto block=file.read(65536);
        if (block.isEmpty() && file.error()!=QFileDevice::NoError) fail("Failed reading export file: "+path);
        hash.addData(block);
    }
    if (!(before==stamp(file))) fail("Export file changed during inspection: "+path);
    QFile named(path); openRegular(named);
    if (!(before==stamp(named))) fail("Export file was replaced during inspection: "+path);
    auto result=before.identity; result.sha256=hash.result(); return result;
}
KisExportFileIdentity directoryIdentity(const QString &path)
{
    const QFileInfo info(path);
    if (!info.isDir() || info.isSymLink()) fail("Export parent is missing or is a symbolic link: "+path);
#ifdef Q_OS_WIN
    HANDLE handle=CreateFileW(reinterpret_cast<LPCWSTR>(path.utf16()),FILE_READ_ATTRIBUTES,
        FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,nullptr,OPEN_EXISTING,FILE_FLAG_BACKUP_SEMANTICS|FILE_FLAG_OPEN_REPARSE_POINT,nullptr);
    if (handle==INVALID_HANDLE_VALUE) fail("Cannot inspect export parent: "+path);
    BY_HANDLE_FILE_INFORMATION stamp{};
    const bool valid=GetFileInformationByHandle(handle,&stamp) && (stamp.dwFileAttributes&FILE_ATTRIBUTE_DIRECTORY) && !(stamp.dwFileAttributes&FILE_ATTRIBUTE_REPARSE_POINT);
    CloseHandle(handle);
    if (!valid) fail("Export parent is not a plain directory: "+path);
    return {stamp.dwVolumeSerialNumber,(quint64(stamp.nFileIndexHigh)<<32)|stamp.nFileIndexLow,0,{}};
#else
    struct stat stamp{};
    if (lstat(QFile::encodeName(path).constData(),&stamp)!=0 || !S_ISDIR(stamp.st_mode)) fail("Cannot inspect export parent: "+path);
    return {quint64(stamp.st_dev),quint64(stamp.st_ino),0,{}};
#endif
}
bool exists(const QString &path) { const QFileInfo info(path); return info.exists() || info.isSymLink(); }
QString canonicalDestination(const QString &path)
{
    const QFileInfo info(QDir::cleanPath(QFileInfo(path).absoluteFilePath()));
    const auto parent=info.dir().canonicalPath();
    if (parent.isEmpty() || info.fileName().isEmpty()) fail("Export parent does not exist: "+path);
    return QDir(parent).filePath(info.fileName());
}
void moveNoReplace(const QString &source,const QString &target)
{
#ifdef Q_OS_WIN
    if (!MoveFileExW(reinterpret_cast<LPCWSTR>(source.utf16()),reinterpret_cast<LPCWSTR>(target.utf16()),MOVEFILE_WRITE_THROUGH)) fail("Cannot publish or restore without replacing an existing file: "+target);
#elif defined(Q_OS_MACOS)
    if (renamex_np(QFile::encodeName(source).constData(),QFile::encodeName(target).constData(),RENAME_EXCL)!=0) fail("Cannot publish or restore without replacing an existing file: "+target);
#elif defined(Q_OS_LINUX) && defined(SYS_renameat2)
    if (syscall(SYS_renameat2,AT_FDCWD,QFile::encodeName(source).constData(),AT_FDCWD,QFile::encodeName(target).constData(),1)!=0) fail("Cannot publish or restore without replacing an existing file: "+target);
#else
    Q_UNUSED(source); Q_UNUSED(target);
    fail("Atomic no-replace publication is unavailable on this platform.");
#endif
}
}
KisExportDestination KisExportDestination::capture(const QString &selected)
{
    KisExportDestination result; result.path=canonicalDestination(selected);
    if (exists(result.path)) result.existing=inspect(result.path);
    auto directory=QFileInfo(result.path).absolutePath();
    for (;;) {
        result.directories.append({directory,directoryIdentity(directory)});
        const auto parent=QFileInfo(directory).absolutePath();
        if (parent==directory) break;
        directory=parent;
    }
    return result;
}
void KisExportDestination::validate() const
{
    if (path.isEmpty() || directories.isEmpty()) fail("No export destination was captured.");
    for (const auto &directory:directories) if (!directoryIdentity(directory.first).sameFile(directory.second)) fail("Export directory changed; choose the destination again: "+directory.first);
    if (existing) {
        if (!overwriteConfirmed) fail("Replacement was not confirmed for: "+path);
        if (inspect(path)!=*existing) fail("The confirmed export target changed; choose the destination again: "+path);
    } else if (exists(path)) fail("The new filename is now occupied; its file was retained: "+path);
}
KisExportFileTransaction::KisExportFileTransaction(const KisExportDestination &destination,const QStringList &protectedPaths)
    :m_destination(destination)
{
    for (const auto &source:protectedPaths) {
        if (source.isEmpty()) continue;
        const auto canonical=canonicalDestination(source);
        m_protected.append({canonical,exists(canonical)?std::optional<KisExportFileIdentity>(inspect(canonical)):std::nullopt});
    }
    checkProtected(); m_destination.validate();
    QTemporaryDir directory(QFileInfo(m_destination.path).absolutePath()+"/.brushquay-export-XXXXXX");
    directory.setAutoRemove(false);
    if (!directory.isValid()) fail("Cannot stage export beside: "+m_destination.path);
    m_staged=directory.path()+"/rendered."+QFileInfo(m_destination.path).suffix();
    m_previous=directory.path()+"/previous-output."+QFileInfo(m_destination.path).suffix();
}
void KisExportFileTransaction::checkProtected() const
{
    std::optional<KisExportFileIdentity> target;
    if (exists(m_destination.path)) target=inspect(m_destination.path);
    for (const auto &source:m_protected) {
        if (source.first==m_destination.path) fail("Export would replace the source document: "+source.first);
        if (source.second) {
            const auto current=inspect(source.first);
            if (current!=*source.second) fail("Protected source changed during export: "+source.first);
            if (target && target->sameFile(current)) fail("Export destination is a hardlink to the source: "+source.first);
        } else if (exists(source.first)) fail("A protected source path appeared during export: "+source.first);
    }
}
KisExportFileOutcome KisExportFileTransaction::finish(bool exportSucceeded,const std::function<bool()> &cancelled)
{
    KisExportFileOutcome result; result.outputPath=m_destination.path; result.stagedPath=m_staged;
    if (m_finished) { result.error="This export run already finished."; return result; }
    m_finished=true; bool displaced=false;
    const auto checkCancel=[&] { if (cancelled && cancelled()) { result.cancelled=true; fail("Export cancelled; existing files were preserved."); } };
    try {
        checkCancel();
        if (!exportSucceeded) fail("Image export failed. Any staged output was retained for inspection: "+m_staged);
        const auto rendered=inspect(m_staged);
        if (rendered.size==0) fail("Image export produced no bytes: "+m_staged);
        checkProtected(); m_destination.validate(); checkCancel();
        if (m_destination.existing) {
            moveNoReplace(m_destination.path,m_previous); displaced=true; result.previousPath=m_previous;
            // Validate the file actually moved, not just the pathname checked before the move.
            if (inspect(m_previous)!=*m_destination.existing) fail("The moved target did not match replacement consent.");
        }
        checkCancel(); checkProtected();
        for (const auto &directory:m_destination.directories) if (!directoryIdentity(directory.first).sameFile(directory.second)) fail("Export directory changed before publication.");
        if (inspect(m_staged)!=rendered) fail("Staged export changed before publication.");
        moveNoReplace(m_staged,m_destination.path); result.published=true; result.stagedPath.clear();
        if (inspect(m_destination.path)!=rendered) fail("Published export changed during final verification. Inspect the output and retained previous file.");
    } catch (const std::exception &error) {
        result.error=QString::fromUtf8(error.what());
        if (displaced && !result.published) {
            try { moveNoReplace(m_previous,m_destination.path); result.previousPath.clear(); }
            catch (const std::exception &restore) { result.error+="\nPrevious file retained at "+m_previous+". "+QString::fromUtf8(restore.what()); }
        }
    }
    return result;
}
