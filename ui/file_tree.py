from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem

from models import CourseData, ResourceItem, Section
from utils import bytes_to_human

COL_NAME = 0
COL_TYPE = 1
COL_SIZE = 2

TYPE_ICON = {
    'video': '🎬',
    'pdf': '📄',
    'document': '📝',
    'image': '🖼',
    'zip': '🗜',
    'file': '📦',
}


class FileTreeWidget(QTreeWidget):
    selection_changed = pyqtSignal(int, 'long long')  # count, total_bytes

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(['Name / Section', 'Type', 'Size'])
        self.setColumnWidth(COL_NAME, 420)
        self.setColumnWidth(COL_TYPE, 80)
        self.setColumnWidth(COL_SIZE, 100)
        self.setAlternatingRowColors(True)
        self.setAnimated(True)
        self.setUniformRowHeights(True)

        header = self.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(COL_NAME, header.ResizeMode.Stretch)

        self.course_data: CourseData | None = None
        self._block_signals = False

        self.itemChanged.connect(self._on_item_changed)

    # ------------------------------------------------------------------ #
    def load_course(self, course: CourseData):
        self.course_data = course
        self._block_signals = True
        self.clear()

        bold = QFont()
        bold.setBold(True)
        section_bg = QColor('#1e3a5f')
        section_fg = QColor('#ffffff')

        for section in course.sections:
            sec_item = QTreeWidgetItem(self)
            sec_item.setText(COL_NAME, f'  {section.name}')
            sec_item.setText(COL_TYPE, f'{len(section.items)} files')
            sec_item.setText(COL_SIZE, bytes_to_human(section.total_size_bytes))
            sec_item.setFont(COL_NAME, bold)
            sec_item.setForeground(COL_NAME, section_fg)
            sec_item.setBackground(COL_NAME, section_bg)
            sec_item.setBackground(COL_TYPE, section_bg)
            sec_item.setForeground(COL_TYPE, section_fg)
            sec_item.setBackground(COL_SIZE, section_bg)
            sec_item.setForeground(COL_SIZE, section_fg)
            sec_item.setCheckState(COL_NAME, Qt.CheckState.Checked)
            sec_item.setData(0, Qt.ItemDataRole.UserRole, section)

            for res in section.items:
                res_item = QTreeWidgetItem(sec_item)
                icon = TYPE_ICON.get(res.resource_type.lower(), '📦')
                res_item.setText(COL_NAME, f'  {icon}  {res.title}')
                res_item.setText(COL_TYPE, res.resource_type)
                res_item.setText(COL_SIZE, res.file_size_str or '? B')
                res_item.setCheckState(COL_NAME, Qt.CheckState.Checked)
                res_item.setData(0, Qt.ItemDataRole.UserRole, res)
                res_item.setToolTip(COL_NAME, res.url)

            sec_item.setExpanded(True)

        self._block_signals = False
        self._emit_selection()

    # ------------------------------------------------------------------ #
    def _on_item_changed(self, item: QTreeWidgetItem, col: int):
        if self._block_signals or col != COL_NAME:
            return
        self._block_signals = True

        state = item.checkState(COL_NAME)
        # If section-level, cascade to children
        if item.parent() is None:
            for i in range(item.childCount()):
                item.child(i).setCheckState(COL_NAME, state)
        else:
            # Update parent tristate
            parent = item.parent()
            checked = sum(
                1 for i in range(parent.childCount())
                if parent.child(i).checkState(COL_NAME) == Qt.CheckState.Checked
            )
            total = parent.childCount()
            if checked == 0:
                parent.setCheckState(COL_NAME, Qt.CheckState.Unchecked)
            elif checked == total:
                parent.setCheckState(COL_NAME, Qt.CheckState.Checked)
            else:
                parent.setCheckState(COL_NAME, Qt.CheckState.PartiallyChecked)

        self._block_signals = False
        self._emit_selection()

    def _emit_selection(self):
        count, total = self.get_selected_stats()
        self.selection_changed.emit(count, total)

    def get_selected_stats(self) -> tuple[int, int]:
        count = 0
        total_bytes = 0
        for i in range(self.topLevelItemCount()):
            sec = self.topLevelItem(i)
            for j in range(sec.childCount()):
                child = sec.child(j)
                if child.checkState(COL_NAME) == Qt.CheckState.Checked:
                    res: ResourceItem = child.data(0, Qt.ItemDataRole.UserRole)
                    count += 1
                    total_bytes += res.file_size_bytes
        return count, total_bytes

    def get_selected_items(self) -> list[tuple[ResourceItem, str]]:
        """Returns list of (ResourceItem, section_folder_name)."""
        result = []
        for i in range(self.topLevelItemCount()):
            sec_item = self.topLevelItem(i)
            section: Section = sec_item.data(0, Qt.ItemDataRole.UserRole)
            for j in range(sec_item.childCount()):
                child = sec_item.child(j)
                if child.checkState(COL_NAME) == Qt.CheckState.Checked:
                    res: ResourceItem = child.data(0, Qt.ItemDataRole.UserRole)
                    result.append((res, section.name))
        return result

    def select_all(self, checked: bool):
        self._block_signals = True
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(self.topLevelItemCount()):
            sec = self.topLevelItem(i)
            sec.setCheckState(COL_NAME, state)
            for j in range(sec.childCount()):
                sec.child(j).setCheckState(COL_NAME, state)
        self._block_signals = False
        self._emit_selection()
