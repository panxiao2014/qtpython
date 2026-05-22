"""
RSS Listing Example - PySide6 版本
对应 Qt 官方示例：https://doc.qt.io/qt-6/qtnetwork-rsslisting-example.html

依赖：
    pip install PySide6
"""

import sys

from PySide6.QtCore import QUrl, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QXmlStreamReader


class RSSListing(QWidget):
    """获取并展示 RSS Feed 条目的主窗口部件。"""

    def __init__(self, url: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # ── 网络 ──────────────────────────────────────────────
        self._manager = QNetworkAccessManager(self)
        self._manager.finished.connect(self._on_finished)
        self._current_reply: QNetworkReply | None = None

        # ── XML 解析状态 ──────────────────────────────────────
        self._xml = QXmlStreamReader()
        self._current_tag = ""
        self._link_string = ""
        self._title_string = ""

        # ── UI ────────────────────────────────────────────────
        self._line_edit = QLineEdit(url, self)
        self._line_edit.setPlaceholderText("输入 RSS Feed URL，然后按回车或点击 Fetch")
        self._line_edit.returnPressed.connect(self.fetch)

        self._fetch_button = QPushButton("Fetch", self)
        self._fetch_button.clicked.connect(self.fetch)

        self._tree_widget = QTreeWidget(self)
        self._tree_widget.setHeaderLabels(["Title", "Link"])
        self._tree_widget.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        self._tree_widget.itemActivated.connect(self._open_url)

        top_bar = QHBoxLayout()
        top_bar.addWidget(self._line_edit)
        top_bar.addWidget(self._fetch_button)

        layout = QVBoxLayout(self)
        layout.addLayout(top_bar)
        layout.addWidget(self._tree_widget)

        self.setWindowTitle("RSS Listing Example (PySide6)")
        self.resize(800, 520)

    # ── 公开槽 ────────────────────────────────────────────────

    @Slot()
    def fetch(self) -> None:
        """用户点击 Fetch 或按下回车时触发，开始下载 RSS 数据。"""
        self._line_edit.setReadOnly(True)
        self._fetch_button.setEnabled(False)
        self._tree_widget.clear()
        self._get(QUrl(self._line_edit.text()))

    @Slot()
    def _consume_data(self) -> None:
        """readyRead 信号触发：检查状态码后增量解析 XML。"""
        if self._current_reply is None:
            return
        status = self._current_reply.attribute(
            QNetworkRequest.Attribute.HttpStatusCodeAttribute
        )
        if status is not None and 200 <= int(status) < 300:
            self._parse_xml()

    @Slot(QNetworkReply.NetworkError)
    def _on_error(self, error_code: QNetworkReply.NetworkError) -> None:
        """网络错误时清理状态并打印警告。"""
        print(f"[警告] 获取 RSS Feed 时出错：{error_code}")
        self._xml.clear()
        if self._current_reply is not None:
            self._current_reply.readyRead.disconnect(self._consume_data)
            self._current_reply.errorOccurred.disconnect(self._on_error)
            self._current_reply.deleteLater()
            self._current_reply = None

    @Slot(QNetworkReply)
    def _on_finished(self, reply: QNetworkReply) -> None:
        """请求完成（无论成功还是失败）后恢复 UI 状态。"""
        self._line_edit.setReadOnly(False)
        self._fetch_button.setEnabled(True)

    # ── 私有方法 ──────────────────────────────────────────────

    def _get(self, url: QUrl) -> None:
        """发起一个 HTTP GET 请求，并将 reply 绑定到 XML 读取器。"""
        # 清理上一次的 reply
        if self._current_reply is not None:
            self._current_reply.readyRead.disconnect(self._consume_data)
            self._current_reply.errorOccurred.disconnect(self._on_error)
            self._current_reply.deleteLater()
            self._current_reply = None

        if url.isValid():
            request = QNetworkRequest(url)
            # 设置 User-Agent，避免某些服务器拒绝默认请求
            request.setHeader(
                QNetworkRequest.KnownHeaders.UserAgentHeader,
                "PySide6-RSSListing/1.0",
            )
            self._current_reply = self._manager.get(request)
            self._current_reply.readyRead.connect(self._consume_data)
            self._current_reply.errorOccurred.connect(self._on_error)
            # 将 reply（QIODevice）设置为 XML 读取器的数据来源
            self._xml.setDevice(self._current_reply)
        else:
            # url 无效时相当于 clear()
            self._xml.setDevice(None)  # type: ignore[arg-type]

    def _parse_xml(self) -> None:
        """增量解析 XML 流，每解析完一个 <item> 就向列表添加一行。"""
        while not self._xml.atEnd():
            self._xml.readNext()

            if self._xml.isStartElement():
                name = self._xml.name()
                if name == "item":
                    # 优先使用 rss:about 属性作为链接（RDF/RSS 1.0 风格）
                    self._link_string = (
                        self._xml.attributes().value("rss:about") or ""
                    )
                    self._title_string = ""
                self._current_tag = name

            elif self._xml.isEndElement():
                if self._xml.name() == "item":
                    item = QTreeWidgetItem()
                    item.setText(0, self._title_string.strip())
                    item.setText(1, self._link_string.strip())
                    self._tree_widget.addTopLevelItem(item)

            elif self._xml.isCharacters() and not self._xml.isWhitespace():
                text = self._xml.text()
                if self._current_tag == "title":
                    self._title_string += text
                elif self._current_tag == "link":
                    # 仅在尚未通过 rss:about 获得链接时才使用 <link> 元素
                    if not self._link_string:
                        self._link_string += text

        # 忽略"文档尚未结束"的良性错误（数据还在路上）
        if (
            self._xml.hasError()
            and self._xml.error()
            != QXmlStreamReader.Error.PrematureEndOfDocumentError
        ):
            print(
                f"[XML 错误] 第 {self._xml.lineNumber()} 行：{self._xml.errorString()}"
            )

    # ── 辅助槽 ────────────────────────────────────────────────

    @Slot(QTreeWidgetItem)
    def _open_url(self, item: QTreeWidgetItem) -> None:
        """双击列表项时用系统默认浏览器打开对应链接。"""
        url = QUrl(item.text(1))
        if url.isValid():
            QDesktopServices.openUrl(url)


# ── 入口 ──────────────────────────────────────────────────────

def main() -> None:
    app = QApplication(sys.argv)
    window = RSSListing("https://www.qt.io/blog/rss.xml")
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()