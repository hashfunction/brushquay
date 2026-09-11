/* SPDX-FileCopyrightText: 2026 Trieflow LLC
 * SPDX-License-Identifier: GPL-3.0-or-later */
#include <QCoreApplication>
#include <QImage>
#include <QPainter>
#include <QSvgRenderer>
int main(int argc,char **argv) {
    QCoreApplication app(argc,argv);
    if (argc!=5) return 2;
    QSvgRenderer svg(QString::fromLocal8Bit(argv[1])); if (!svg.isValid()) return 3;
    const QSize size(QString::fromLocal8Bit(argv[3]).toInt(),QString::fromLocal8Bit(argv[4]).toInt());
    if (size.width()<1 || size.height()<1 || size.width()>2048 || size.height()>2048) return 4;
    QImage image(size,QImage::Format_ARGB32_Premultiplied); image.fill(Qt::transparent);
    QPainter painter(&image); svg.render(&painter); painter.end();
    return image.save(QString::fromLocal8Bit(argv[2]),"PNG")?0:5;
}
