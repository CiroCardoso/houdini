"""
===============================================================================
Tool:        parm_transfer.py
Version:     1.0.0
Author:      Ciro Cardoso
Updated:     2026-01-28

A tool to compare and selectively copy parameters between nodes.

CHANGELOG:
1.0.0 - Initial version.
===============================================================================
"""

import hou
from PySide2 import QtWidgets, QtCore, QtGui # to make it work in houdini 21, replace PySide2 for PySide6

class ParameterItem:
    """Data class for parameter information."""
    def __init__(self, parm):
        self.parm = parm
        self.name = parm.name()
        self.label = parm.description()
        self.parm_template = parm.parmTemplate()
        self.is_at_default = parm.isAtDefault()

        self.value = self._get_value()
        self.value_display = self._get_display_value()

        self.has_keyframes = parm.isTimeDependent()

        self.has_expression = False
        if not self.has_keyframes:
            try:
                parm.expression()
                self.has_expression = True
            except hou.OperationFailed:
                pass
        
    def _get_value(self):
        """Get parameter value."""
        try:
            return self.parm.eval()
        except:
            try:
                return self.parm.unexpandedString()
            except:
                return None
                
    def _get_display_value(self):
        """Get a display-friendly value string."""
        try:
            parm_type = self.parm_template.type()
            
            if parm_type == hou.parmTemplateType.Menu:
                
                try:
                    menu_items = self.parm_template.menuLabels()
                    idx = int(self.parm.eval())
                    if 0 <= idx < len(menu_items):
                        return f"{menu_items[idx]} ({idx})"
                except:
                    pass
                    
            elif parm_type == hou.parmTemplateType.Toggle:
                return "On" if self.parm.eval() else "Off"
                
            elif parm_type == hou.parmTemplateType.String:
                val = self.parm.eval()
                if len(val) > 50:
                    return val[:47] + "..."
                return val
                
            elif parm_type == hou.parmTemplateType.Ramp:
                return "[Ramp Data]"
                
            val = self.parm.eval()
            if isinstance(val, float):
                return f"{val:.6g}"
            return str(val)
            
        except:
            return str(self.value)

class ParameterTableModel(QtCore.QAbstractTableModel):
    """Table model for parameter display."""
    
    COLUMNS = ["", "Name", "Label", "Value", "Status"]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parameters = []
        self.checked_items = set()
        self.show_only_non_default = False
        self.filter_text = ""
        self._filtered_indices = []
        
    def set_parameters(self, parm_items):
        """Set the parameter list."""
        self.beginResetModel()
        self.parameters = parm_items
        self.checked_items.clear()
        self._update_filtered_indices()
        self.endResetModel()
        
    def _update_filtered_indices(self):
        """Update the list of visible row indices based on filters."""
        self._filtered_indices = []
        for i, parm_item in enumerate(self.parameters):
            if self._matches_filter(parm_item):
                self._filtered_indices.append(i)
                
    def _matches_filter(self, parm_item):
        """Check if parameter matches current filters."""
        if self.show_only_non_default and parm_item.is_at_default:
            return False
            
        if self.filter_text:
            search = self.filter_text.lower()
            if (search not in parm_item.name.lower() and 
                search not in parm_item.label.lower()):
                return False
                
        return True
        
    def set_filter(self, text):
        """Set text filter."""
        self.beginResetModel()
        self.filter_text = text
        self._update_filtered_indices()
        self.endResetModel()
        
    def set_show_only_non_default(self, enabled):
        """Toggle showing only non-default parameters."""
        self.beginResetModel()
        self.show_only_non_default = enabled
        self._update_filtered_indices()
        self.endResetModel()
        
    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self._filtered_indices)
        
    def columnCount(self, parent=QtCore.QModelIndex()):
        return len(self.COLUMNS)
        
    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return self.COLUMNS[section]
        return None
        
    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None
            
        real_idx = self._filtered_indices[index.row()]
        parm_item = self.parameters[real_idx]
        col = index.column()
        
        if role == QtCore.Qt.DisplayRole:
            if col == 0:  # Checkbox column
                return None
            elif col == 1:  # Name
                return parm_item.name
            elif col == 2:  # Label
                return parm_item.label
            elif col == 3:  # Value
                return parm_item.value_display
            elif col == 4:  # Status
                status = []
                if parm_item.has_keyframes:
                    status.append("🔑 Animated")
                if parm_item.has_expression:
                    status.append("⚡ Expression")
                if not parm_item.is_at_default:
                    status.append("✏️ Modified")
                return " | ".join(status) if status else "Default"
                
        elif role == QtCore.Qt.CheckStateRole:
            if col == 0:
                return QtCore.Qt.Checked if real_idx in self.checked_items else QtCore.Qt.Unchecked
                
        elif role == QtCore.Qt.ForegroundRole:
            if not parm_item.is_at_default:
                return QtGui.QColor(255, 200, 100)
            if parm_item.has_keyframes or parm_item.has_expression:
                return QtGui.QColor(150, 200, 255)
                
        elif role == QtCore.Qt.ToolTipRole:
            tooltip = f"Parameter: {parm_item.name}\n"
            tooltip += f"Label: {parm_item.label}\n"
            tooltip += f"Value: {parm_item.value_display}\n"
            if parm_item.has_expression:
                try:
                    tooltip += f"Expression: {parm_item.parm.expression()}"
                except:
                    pass
            return tooltip
            
        return None
        
    def setData(self, index, value, role=QtCore.Qt.EditRole):
        if role == QtCore.Qt.CheckStateRole and index.column() == 0:
            real_idx = self._filtered_indices[index.row()]
            if value == QtCore.Qt.Checked:
                self.checked_items.add(real_idx)
            else:
                self.checked_items.discard(real_idx)
            self.dataChanged.emit(index, index)
            return True
        return False
        
    def flags(self, index):
        flags = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
        if index.column() == 0:
            flags |= QtCore.Qt.ItemIsUserCheckable
        return flags
        
    def get_checked_parameters(self):
        """Return list of checked ParameterItem objects."""
        return [self.parameters[i] for i in self.checked_items]
        
    def check_all_visible(self):
        """Check all currently visible items."""
        self.beginResetModel()
        for idx in self._filtered_indices:
            self.checked_items.add(idx)
        self.endResetModel()
        
    def uncheck_all(self):
        """Uncheck all items."""
        self.beginResetModel()
        self.checked_items.clear()
        self.endResetModel()
        
    def check_non_default(self):
        """Check only non-default parameters."""
        self.beginResetModel()
        self.checked_items.clear()
        for i, parm_item in enumerate(self.parameters):
            if not parm_item.is_at_default:
                self.checked_items.add(i)
        self.endResetModel()

class NodePickerWidget(QtWidgets.QWidget):
    """Widget for selecting a Houdini node."""
    
    node_changed = QtCore.Signal(object)
    
    def __init__(self, label="Node:", parent=None):
        super().__init__(parent)
        self._node = None
        self._setup_ui(label)
        
    def _setup_ui(self, label):
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.label = QtWidgets.QLabel(label)
        self.label.setMinimumWidth(80)
        layout.addWidget(self.label)
        
        self.path_edit = QtWidgets.QLineEdit()
        self.path_edit.setPlaceholderText("Enter node path or pick from selection...")
        self.path_edit.editingFinished.connect(self._on_path_edited)
        layout.addWidget(self.path_edit)
        
        self.pick_btn = QtWidgets.QPushButton("◎ Pick")
        self.pick_btn.setToolTip("Pick from current network selection")
        self.pick_btn.setFixedWidth(100)
        self.pick_btn.clicked.connect(self._pick_from_selection)
        layout.addWidget(self.pick_btn)
        
        self.clear_btn = QtWidgets.QPushButton("✕")
        self.clear_btn.setToolTip("Clear selection")
        self.clear_btn.setFixedWidth(30)
        self.clear_btn.clicked.connect(self.clear)
        layout.addWidget(self.clear_btn)
        
    def _on_path_edited(self):
        """Handle manual path entry."""
        path = self.path_edit.text().strip()
        if not path:
            self.set_node(None)
            return
            
        try:
            node = hou.node(path)
            if node:
                self.set_node(node)
            else:
                self.path_edit.setStyleSheet("background-color: #662222;")
        except:
            self.path_edit.setStyleSheet("background-color: #662222;")
            
    def _pick_from_selection(self):
        """Pick node from current network selection."""
        selected = hou.selectedNodes()
        if selected:
            self.set_node(selected[0])
        else:
            hou.ui.displayMessage("Please select a node in the network editor first.",
                                  title="No Selection")
            
    def set_node(self, node):
        """Set the current node."""
        self._node = node
        if node:
            self.path_edit.setText(node.path())
            self.path_edit.setStyleSheet("")
        else:
            self.path_edit.setText("")
            self.path_edit.setStyleSheet("")
        self.node_changed.emit(node)
        
    def get_node(self):
        """Get the current node."""
        return self._node
        
    def clear(self):
        """Clear the node selection."""
        self.set_node(None)

class MultiNodePickerWidget(QtWidgets.QWidget):
    """Widget for selecting multiple Houdini nodes."""
    
    nodes_changed = QtCore.Signal(list)
    
    def __init__(self, label="Target Nodes:", parent=None):
        super().__init__(parent)
        self._nodes = []
        self._setup_ui(label)
        
    def _setup_ui(self, label):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header row
        header_layout = QtWidgets.QHBoxLayout()
        
        self.label = QtWidgets.QLabel(label)
        header_layout.addWidget(self.label)
        
        header_layout.addStretch()
        
        self.pick_btn = QtWidgets.QPushButton("◎ Add from Selection")
        self.pick_btn.clicked.connect(self._pick_from_selection)
        header_layout.addWidget(self.pick_btn)
        
        self.clear_btn = QtWidgets.QPushButton("Clear All")
        self.clear_btn.clicked.connect(self.clear)
        header_layout.addWidget(self.clear_btn)
        
        layout.addLayout(header_layout)
        
        self.node_list = QtWidgets.QListWidget()
        self.node_list.setMaximumHeight(100)
        self.node_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.node_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.node_list.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.node_list)
        
    def _pick_from_selection(self):
        """Add nodes from current network selection."""
        selected = hou.selectedNodes()
        if not selected:
            hou.ui.displayMessage("Please select one or more nodes in the network editor.",
                                  title="No Selection")
            return
            
        for node in selected:
            if node not in self._nodes:
                self._nodes.append(node)
                self.node_list.addItem(node.path())
                
        self.nodes_changed.emit(self._nodes)
        
    def _show_context_menu(self, pos):
        """Show context menu for node list."""
        menu = QtWidgets.QMenu(self)
        
        remove_action = menu.addAction("Remove Selected")
        remove_action.triggered.connect(self._remove_selected)
        
        menu.exec_(self.node_list.mapToGlobal(pos))
        
    def _remove_selected(self):
        """Remove selected items from the list."""
        for item in self.node_list.selectedItems():
            row = self.node_list.row(item)
            self.node_list.takeItem(row)
            del self._nodes[row]
        self.nodes_changed.emit(self._nodes)
        
    def get_nodes(self):
        """Get the list of selected nodes."""
        
        valid_nodes = []
        for node in self._nodes:
            try:
                _ = node.path()
                valid_nodes.append(node)
            except:
                pass
        self._nodes = valid_nodes
        return self._nodes
        
    def clear(self):
        """Clear all nodes."""
        self._nodes = []
        self.node_list.clear()
        self.nodes_changed.emit(self._nodes)

class ParameterTransferPanel(QtWidgets.QWidget):
    """Main panel for parameter comparison and transfer."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Parameter Transfer")
        self.setMinimumSize(800, 600)
        self._source_node = None
        self._setup_ui()
        
    def _setup_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        
        source_group = QtWidgets.QGroupBox("Source Node")
        source_layout = QtWidgets.QVBoxLayout(source_group)
        
        self.source_picker = NodePickerWidget("Source:")
        self.source_picker.node_changed.connect(self._on_source_changed)
        source_layout.addWidget(self.source_picker)
        
        main_layout.addWidget(source_group)
        
        filter_layout = QtWidgets.QHBoxLayout()
        
        filter_layout.addWidget(QtWidgets.QLabel("Filter:"))
        
        self.filter_edit = QtWidgets.QLineEdit()
        self.filter_edit.setPlaceholderText("Type to filter parameters...")
        self.filter_edit.textChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.filter_edit)
        
        self.non_default_check = QtWidgets.QCheckBox("Show only modified")
        self.non_default_check.toggled.connect(self._on_non_default_toggled)
        filter_layout.addWidget(self.non_default_check)
        
        main_layout.addLayout(filter_layout)
        
        select_layout = QtWidgets.QHBoxLayout()
        
        self.select_all_btn = QtWidgets.QPushButton("Select All Visible")
        self.select_all_btn.clicked.connect(self._select_all_visible)
        select_layout.addWidget(self.select_all_btn)
        
        self.select_none_btn = QtWidgets.QPushButton("Select None")
        self.select_none_btn.clicked.connect(self._select_none)
        select_layout.addWidget(self.select_none_btn)
        
        self.select_modified_btn = QtWidgets.QPushButton("Select Modified")
        self.select_modified_btn.clicked.connect(self._select_modified)
        select_layout.addWidget(self.select_modified_btn)
        
        select_layout.addStretch()
        
        self.selected_count_label = QtWidgets.QLabel("0 parameters selected")
        select_layout.addWidget(self.selected_count_label)
        
        main_layout.addLayout(select_layout)
        
        self.table_model = ParameterTableModel()
        self.table_model.dataChanged.connect(self._update_selection_count)
        
        self.table_view = QtWidgets.QTableView()
        self.table_view.setModel(self.table_model)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table_view.setSortingEnabled(False)
        self.table_view.setWordWrap(False)
        
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Fixed)
        header.resizeSection(0, 30)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Interactive)
        header.resizeSection(1, 150)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.Interactive)
        header.resizeSection(2, 150)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.Interactive)
        header.resizeSection(3, 150)
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.Stretch)
        
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.verticalHeader().setDefaultSectionSize(24)
        
        main_layout.addWidget(self.table_view)
        
        target_group = QtWidgets.QGroupBox("Target Nodes")
        target_layout = QtWidgets.QVBoxLayout(target_group)
        
        self.target_picker = MultiNodePickerWidget("Targets:")
        target_layout.addWidget(self.target_picker)
        
        main_layout.addWidget(target_group)
        
        options_group = QtWidgets.QGroupBox("Transfer Options")
        options_layout = QtWidgets.QHBoxLayout(options_group)
        
        self.copy_expressions_check = QtWidgets.QCheckBox("Copy expressions")
        self.copy_expressions_check.setChecked(True)
        self.copy_expressions_check.setToolTip("If checked, copies expressions. Otherwise copies evaluated values.")
        options_layout.addWidget(self.copy_expressions_check)
        
        self.copy_keyframes_check = QtWidgets.QCheckBox("Copy keyframes")
        self.copy_keyframes_check.setChecked(True)
        self.copy_keyframes_check.setToolTip("If checked, copies all keyframes. Otherwise copies current frame value.")
        options_layout.addWidget(self.copy_keyframes_check)
        
        self.skip_locked_check = QtWidgets.QCheckBox("Skip locked parameters")
        self.skip_locked_check.setChecked(True)
        options_layout.addWidget(self.skip_locked_check)
        
        options_layout.addStretch()
        
        main_layout.addWidget(options_group)
        
        transfer_layout = QtWidgets.QHBoxLayout()
        transfer_layout.addStretch()
        
        self.transfer_btn = QtWidgets.QPushButton("  Transfer Selected Parameters  ")
        self.transfer_btn.setStyleSheet("""
            QPushButton {
                background-color: #445544;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #557755;
            }
            QPushButton:pressed {
                background-color: #336633;
            }
        """)
        self.transfer_btn.clicked.connect(self._do_transfer)
        transfer_layout.addWidget(self.transfer_btn)
        
        transfer_layout.addStretch()
        main_layout.addLayout(transfer_layout)
        
        self.status_label = QtWidgets.QLabel("Select a source node to begin")
        self.status_label.setStyleSheet("color: #888888; padding: 5px;")
        main_layout.addWidget(self.status_label)
        
    def _on_source_changed(self, node):
        """Handle source node change."""
        self._source_node = node
        
        if node is None:
            self.table_model.set_parameters([])
            self.status_label.setText("Select a source node to begin")
            return
            
        parm_items = []
        for parm in node.parms():
            template = parm.parmTemplate()
            if template.type() in (hou.parmTemplateType.FolderSet, 
                                    hou.parmTemplateType.Folder,
                                    hou.parmTemplateType.Label,
                                    hou.parmTemplateType.Separator):
                continue
                
            parm_items.append(ParameterItem(parm))
            
        self.table_model.set_parameters(parm_items)
        self._update_selection_count()
        
        non_default = sum(1 for p in parm_items if not p.is_at_default)
        self.status_label.setText(f"Loaded {len(parm_items)} parameters from {node.name()} ({non_default} modified)")
        
    def _on_filter_changed(self, text):
        """Handle filter text change."""
        self.table_model.set_filter(text)
        self._update_selection_count()
        
    def _on_non_default_toggled(self, checked):
        """Handle non-default filter toggle."""
        self.table_model.set_show_only_non_default(checked)
        self._update_selection_count()
        
    def _select_all_visible(self):
        """Select all visible parameters."""
        self.table_model.check_all_visible()
        self._update_selection_count()
        
    def _select_none(self):
        """Deselect all parameters."""
        self.table_model.uncheck_all()
        self._update_selection_count()
        
    def _select_modified(self):
        """Select only modified parameters."""
        self.table_model.check_non_default()
        self._update_selection_count()
        
    def _update_selection_count(self):
        """Update the selection count label."""
        count = len(self.table_model.checked_items)
        self.selected_count_label.setText(f"{count} parameters selected")
        
    def _do_transfer(self):
        """Execute the parameter transfer."""
        
        checked_parms = self.table_model.get_checked_parameters()
        if not checked_parms:
            hou.ui.displayMessage("No parameters selected for transfer.",
                                  title="Nothing Selected")
            return
            
        target_nodes = self.target_picker.get_nodes()
        if not target_nodes:
            hou.ui.displayMessage("No target nodes selected.",
                                  title="No Targets")
            return
            
        msg = f"Transfer {len(checked_parms)} parameters to {len(target_nodes)} node(s)?\n\n"
        msg += "Source: " + self._source_node.path() + "\n"
        msg += "Targets:\n"
        for node in target_nodes[:5]:
            msg += f"  - {node.path()}\n"
        if len(target_nodes) > 5:
            msg += f"  ... and {len(target_nodes) - 5} more\n"
            
        result = hou.ui.displayMessage(msg, 
                                       buttons=("Transfer", "Cancel"),
                                       severity=hou.severityType.ImportantMessage,
                                       title="Confirm Transfer")
        if result != 0:
            return
            
        copy_expressions = self.copy_expressions_check.isChecked()
        copy_keyframes = self.copy_keyframes_check.isChecked()
        skip_locked = self.skip_locked_check.isChecked()
        
        with hou.undos.group("Parameter Transfer"):
            success_count = 0
            skip_count = 0
            fail_count = 0
            
            for target_node in target_nodes:
                for parm_item in checked_parms:
                    result = self._transfer_parameter(
                        parm_item, 
                        target_node,
                        copy_expressions,
                        copy_keyframes,
                        skip_locked
                    )
                    if result == "success":
                        success_count += 1
                    elif result == "skipped":
                        skip_count += 1
                    else:
                        fail_count += 1
                        
        msg = f"Transfer complete!\n\n"
        msg += f"✓ Transferred: {success_count}\n"
        if skip_count > 0:
            msg += f"⊘ Skipped: {skip_count}\n"
        if fail_count > 0:
            msg += f"✗ Failed: {fail_count}\n"
            
        self.status_label.setText(f"Transferred {success_count} parameters to {len(target_nodes)} node(s)")
        hou.ui.displayMessage(msg, title="Transfer Complete")
        
    def _transfer_parameter(self, parm_item, target_node, copy_expressions, copy_keyframes, skip_locked):
        """Transfer a single parameter to a target node."""
        
        source_parm = parm_item.parm
        target_parm = target_node.parm(parm_item.name)
        
        if target_parm is None:
            return "failed"
        
        if skip_locked and (target_parm.isLocked() or source_parm.isLocked()):
            return "skipped"
            
        try:
            
            if copy_keyframes and parm_item.has_keyframes:
                target_parm.deleteAllKeyframes()
                for keyframe in source_parm.keyframes():
                    target_parm.setKeyframe(keyframe)
                return "success"
                
            if copy_expressions and parm_item.has_expression:
                try:
                    expr = source_parm.expression()
                    lang = source_parm.expressionLanguage()
                    target_parm.setExpression(expr, lang)
                    return "success"
                except:
                    pass
                    
            parm_type = parm_item.parm_template.type()
            
            if parm_type == hou.parmTemplateType.String:
                target_parm.set(source_parm.unexpandedString())
            elif parm_type == hou.parmTemplateType.Ramp:
                target_parm.set(source_parm.eval())
            else:
                target_parm.set(source_parm.eval())
                
            return "success"
            
        except Exception as e:
            print(f"Failed to transfer {parm_item.name}: {e}")
            return "failed"


def create_panel():
    """Create and return the panel widget."""
    return ParameterTransferPanel()

def show_dialog():
    """Show the panel as a floating dialog."""
    
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if isinstance(widget, ParameterTransferPanel):
            widget.show()
            widget.raise_()
            widget.activateWindow()
            return widget
            
    dialog = ParameterTransferPanel()
    dialog.setParent(hou.qt.mainWindow(), QtCore.Qt.Window)
    dialog.show()
    return dialog

if __name__ == "__main__":
    show_dialog()