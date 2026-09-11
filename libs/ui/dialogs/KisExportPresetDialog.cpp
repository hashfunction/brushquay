/* SPDX-FileCopyrightText: 2026 Trieflow LLC
 * SPDX-License-Identifier: GPL-3.0-or-later */
#include "KisExportPresetDialog.h"
#include "KisExportPresetCodec.h"
#include "KisDocument.h"
#include "KisImportExportManager.h"
#include <KisMimeDatabase.h>
#include <kis_config_widget.h>
#include <QComboBox>
#include <QDialogButtonBox>
#include <QFormLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QLineEdit>
#include <QListWidget>
#include <QMessageBox>
#include <QPushButton>
#include <QScrollArea>
#include <QSignalBlocker>
#include <QVBoxLayout>
#include <klocalizedstring.h>
#include <utility>

KisExportPresetDialog::KisExportPresetDialog(KisDocument *document,QWidget *parent,QString storePath)
    :QDialog(parent),m_document(document),m_store(std::move(storePath))
{
    setWindowTitle(i18n("Export with Preset")); setMinimumSize(720,540);
    auto *layout=new QVBoxLayout(this);
    auto *intro=new QLabel(i18n("Reuse PNG and JPEG export settings. Choose the destination after reviewing the options."),this);
    intro->setWordWrap(true); layout->addWidget(intro);
    auto *body=new QHBoxLayout; layout->addLayout(body,1);
    auto *left=new QVBoxLayout; body->addLayout(left);
    auto *saved=new QLabel(i18n("Saved &presets"),this); left->addWidget(saved);
    m_list=new QListWidget(this); m_list->setObjectName("savedExportPresets"); m_list->setAccessibleName(i18n("Saved export presets")); saved->setBuddy(m_list); left->addWidget(m_list,1);
    auto *newButton=new QPushButton(i18n("&New Preset"),this); left->addWidget(newButton);
    auto *reloadButton=new QPushButton(i18n("&Reload from Disk"),this); left->addWidget(reloadButton);
    auto *right=new QVBoxLayout; body->addLayout(right,2);
    auto *form=new QFormLayout; right->addLayout(form);
    m_name=new QLineEdit(this); m_name->setObjectName("exportPresetName"); m_name->setMaxLength(160); form->addRow(i18n("Preset &name:"),m_name);
    m_format=new QComboBox(this); m_format->setObjectName("exportPresetFormat"); form->addRow(i18n("&Format:"),m_format);
    const auto available=KisImportExportManager::supportedMimeTypes(KisImportExportManager::Export);
    for (const auto &mime:KisExportPreset::supportedMimeTypes()) if (available.contains(mime)) m_format->addItem(KisMimeDatabase::descriptionForMimeType(mime),mime);
    auto *area=new QScrollArea(this); area->setWidgetResizable(true); right->addWidget(area,1);
    auto *options=new QWidget(area); m_options=new QVBoxLayout(options); area->setWidget(options);
    auto *edits=new QHBoxLayout; right->addLayout(edits);
    m_save=new QPushButton(i18n("&Save Preset"),this); m_save->setObjectName("saveExportPreset"); edits->addWidget(m_save);
    m_delete=new QPushButton(i18n("&Delete Preset"),this); m_delete->setObjectName("deleteExportPreset"); edits->addWidget(m_delete);
    m_message=new QLabel(this); m_message->setWordWrap(true); m_message->setTextFormat(Qt::PlainText); m_message->setTextInteractionFlags(Qt::TextSelectableByMouse|Qt::TextSelectableByKeyboard); layout->addWidget(m_message);
    auto *buttons=new QDialogButtonBox(QDialogButtonBox::Cancel,this); layout->addWidget(buttons);
    m_export=buttons->addButton(i18n("Choose &Destination…"),QDialogButtonBox::AcceptRole); m_export->setObjectName("chooseExportDestination");
    connect(buttons,&QDialogButtonBox::rejected,this,&QDialog::reject);
    connect(m_export,&QPushButton::clicked,this,[this] { auto value=draft(); if (value) { m_selected=*value; accept(); } });
    connect(newButton,&QPushButton::clicked,this,&KisExportPresetDialog::newPreset);
    connect(reloadButton,&QPushButton::clicked,this,&KisExportPresetDialog::reload);
    connect(m_list,&QListWidget::currentRowChanged,this,[this] { selectPreset(); });
    connect(m_format,qOverload<int>(&QComboBox::currentIndexChanged),this,[this] { createEditor(); });
    connect(m_save,&QPushButton::clicked,this,&KisExportPresetDialog::savePreset);
    connect(m_delete,&QPushButton::clicked,this,&KisExportPresetDialog::deletePreset);
    reload();
}
KisExportPresetDialog::~KisExportPresetDialog() { delete m_widget; }
void KisExportPresetDialog::showError(const KisExportPresetResult &error)
{
    m_message->setText(error.message+(error.recoveryPath.isEmpty()?QString():i18n("\nRecovery copy: %1",error.recoveryPath)));
}
void KisExportPresetDialog::reload()
{
    const auto result=m_store.load(); m_loaded=result.ok();
    { QSignalBlocker blocker(m_list); m_list->clear();
      if (m_loaded) for (const auto &p:m_store.presets()) { auto *item=new QListWidgetItem(p.name,m_list); item->setData(Qt::UserRole,p.id.toString()); item->setToolTip(p.mimeType); } }
    m_save->setEnabled(m_loaded); m_delete->setEnabled(false);
    if (!m_loaded) showError(result); else m_message->clear();
    newPreset();
}
void KisExportPresetDialog::newPreset()
{
    { QSignalBlocker blocker(m_list); m_list->setCurrentRow(-1); }
    m_id=QUuid::createUuid(); m_name->setText(i18n("New export preset")); m_delete->setEnabled(false); createEditor();
}
void KisExportPresetDialog::selectPreset()
{
    auto *item=m_list->currentItem(); if (!item) return;
    const auto p=m_store.find(QUuid(item->data(Qt::UserRole).toString())); if (!p) return;
    m_id=p->id; m_name->setText(p->name);
    { QSignalBlocker blocker(m_format); m_format->setCurrentIndex(m_format->findData(p->mimeType)); }
    m_delete->setEnabled(m_loaded); createEditor(&*p);
}
void KisExportPresetDialog::createEditor(const KisExportPreset *preset)
{
    delete m_widget; m_widget=nullptr; m_filter.reset(); m_export->setEnabled(false);
    if (!m_document || !m_document->image()) { m_message->setText(i18n("The source document is no longer open.")); return; }
    const auto mime=m_format->currentData().toString();
    m_filter.reset(KisImportExportManager::filterForMimeType(mime,KisImportExportManager::Export));
    if (!m_filter) { m_message->setText(i18n("The selected export plug-in is unavailable.")); return; }
    KisPropertiesConfigurationSP configuration;
    if (preset) { const auto result=KisExportPresetCodec::restore(*preset,configuration); if (!result.ok()) { showError(result); return; } }
    else configuration=m_filter->defaultConfiguration();
    if (!configuration) return;
    KisImportExportManager::fillStaticExportConfigurationProperties(configuration,m_document->image());
    m_widget=m_filter->createConfigurationWidget(this);
    if (!m_widget) { m_message->setText(i18n("This plug-in has no export options widget.")); return; }
    m_widget->setAccessibleName(i18n("Format export options")); m_widget->setConfiguration(configuration); m_options->addWidget(m_widget);
    m_export->setEnabled(true);
}
std::optional<KisExportPreset> KisExportPresetDialog::draft()
{
    if (!m_widget) return std::nullopt;
    KisExportPreset p; const auto mime=m_format->currentData().toString();
    const auto result=KisExportPresetCodec::capture(m_id,m_name->text(),mime,mime=="image/png"?"png":"jpg",m_widget->configuration(),p);
    if (!result.ok()) { showError(result); return std::nullopt; }
    return p;
}
void KisExportPresetDialog::savePreset()
{
    if (!m_loaded) return;
    const auto p=draft(); if (!p) return;
    const auto result=m_store.save(*p);
    if (!result.ok()) { showError(result); return; }
    reload();
    for (int row=0;row<m_list->count();++row) if (QUuid(m_list->item(row)->data(Qt::UserRole).toString())==p->id) { m_list->setCurrentRow(row); break; }
    m_message->setText(i18n("Preset saved locally."));
}
void KisExportPresetDialog::deletePreset()
{
    if (!m_loaded || !m_store.find(m_id)) return;
    if (QMessageBox::question(this,i18n("Delete Preset"),i18n("Delete “%1” from saved presets?",m_store.find(m_id)->name),QMessageBox::Yes|QMessageBox::Cancel,QMessageBox::Cancel)!=QMessageBox::Yes) return;
    const auto result=m_store.remove(m_id); if (!result.ok()) { showError(result); return; } reload();
}
