/* SPDX-FileCopyrightText: 2026 Trieflow LLC
 * SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef KIS_EXPORT_PRESET_DIALOG_H
#define KIS_EXPORT_PRESET_DIALOG_H
#include <QDialog>
#include <QPointer>
#include <QScopedPointer>
#include "KisExportPresetStore.h"
#include <kritaui_export.h>
class KisDocument;
class KisImportExportFilter;
class KisConfigWidget;
class QListWidget;
class QComboBox;
class QLineEdit;
class QVBoxLayout;
class QLabel;
class QPushButton;
class KRITAUI_EXPORT KisExportPresetDialog : public QDialog {
    Q_OBJECT
public:
    explicit KisExportPresetDialog(KisDocument *,QWidget *parent=nullptr,QString storePath={});
    ~KisExportPresetDialog() override;
    std::optional<KisExportPreset> selectedPreset() const { return m_selected; }
private:
    void reload();
    void newPreset();
    void selectPreset();
    void createEditor(const KisExportPreset *preset=nullptr);
    void showError(const KisExportPresetResult &);
    std::optional<KisExportPreset> draft();
    void savePreset();
    void deletePreset();
    QPointer<KisDocument> m_document;
    KisExportPresetStore m_store;
    QScopedPointer<KisImportExportFilter> m_filter;
    KisConfigWidget *m_widget=nullptr;
    QListWidget *m_list;
    QComboBox *m_format;
    QLineEdit *m_name;
    QVBoxLayout *m_options;
    QLabel *m_message;
    QPushButton *m_save,*m_delete,*m_export;
    QUuid m_id;
    bool m_loaded=false;
    std::optional<KisExportPreset> m_selected;
};
#endif
