"""
Tool Development Kit for SideFX Houdini
Copyright (C) 2021  Ivan Titov

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

from __future__ import print_function

import os

try:
    from PyQt5.QtWidgets import *
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *

    Signal = pyqtSignal
except ImportError:
    from PySide2.QtWidgets import *
    from PySide2.QtGui import *
    from PySide2.QtCore import *

import hou

from .find_icon import FindIconDialog
from .notification import notify


def makeNewHDAFromTemplateNode(template_node, label, name=None, namespace=None, icon=None,
                               sections=None, version='1.0', location='$HOUDINI_USER_PREF_DIR/otls',
                               inherit_subnetwork=True):
    template_node_type = template_node.type()
    if template_node_type.name() != 'tdk::template':
        raise TypeError

    location = hou.expandString(location)
    if not os.path.exists(location) or not os.path.isdir(location):
        raise IOError

    new_type_name = ''

    if namespace:
        new_type_name += namespace.replace(' ', '_').lower() + '::'

    if name:
        new_type_name += name.replace(' ', '_').lower()
    else:
        new_type_name += label.replace(' ', '_').lower()

    new_type_name += '::'

    if version:
        new_type_name += version
    else:
        new_type_name += '1.0'

    template_def = template_node_type.definition()

    new_hda_file_name = new_type_name.replace(':', '_').replace('.', '_') + '.hda'
    new_hda_file_path = os.path.join(location, new_hda_file_name).replace('\\', '/')
    template_def.copyToHDAFile(new_hda_file_path, new_type_name)

    new_def = hou.hda.definitionsInFile(new_hda_file_path)[0]

    if inherit_subnetwork:
        new_def.updateFromNode(template_node)

    new_def.setDescription(label)

    if icon:
        new_def.setIcon(icon)

    tools = new_def.sections()['Tools.shelf']
    content = tools.contents()
    sections = sections or 'Digital Assets'
    try:
        content = content[:content.index('<toolSubmenu>') + len('<toolSubmenu>')] + \
                  sections + content[content.index('</toolSubmenu>'):]
        tools.setContents(content)
    except ValueError:
        pass

    return new_def


class IconField(QWidget):
    def __init__(self):
        super(IconField, self).__init__()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.edit = QLineEdit()
        layout.addWidget(self.edit)

        self.icon_preview = QLabel()
        self.icon_preview.setToolTip('Icon preview')
        self.icon_preview.setFixedSize(24, 24)
        self.icon_preview.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.icon_preview)
        self.edit.textChanged.connect(self.updateIconPreview)

        self.pick_icon_from_disk_button = QPushButton()
        self.pick_icon_from_disk_button.setToolTip('Pick icon from disk')
        self.pick_icon_from_disk_button.setFixedSize(24, 24)
        self.pick_icon_from_disk_button.setIcon(hou.qt.Icon('BUTTONS_chooser_file', 16, 16))
        self.pick_icon_from_disk_button.clicked.connect(self._pickIconFromDisk)
        layout.addWidget(self.pick_icon_from_disk_button)

        self.pick_icon_from_houdini_button = QPushButton()
        self.pick_icon_from_houdini_button.setToolTip('Pick icon from Houdini')
        self.pick_icon_from_houdini_button.setFixedSize(24, 24)
        self.pick_icon_from_houdini_button.setIcon(hou.qt.Icon('OBJ_hlight', 16, 16))
        self.pick_icon_from_houdini_button.clicked.connect(self._pickIconFromHoudini)
        layout.addWidget(self.pick_icon_from_houdini_button)

    def text(self):
        return self.edit.text()

    def updateIconPreview(self):
        icon_file_name = self.edit.text()

        if not icon_file_name:
            self.icon_preview.clear()
            return

        if os.path.isfile(icon_file_name):  # Todo: Limit allowed file size
            _, ext = os.path.splitext(icon_file_name)
            if ext in ('.jpg', '.jpeg', '.png', '.bmp', '.tga', '.tif', '.tiff'):
                image = QImage(icon_file_name)
                self.icon_preview.setPixmap(QPixmap.fromImage(image).scaled(16, 16, Qt.KeepAspectRatio))
            else:  # Fallback to Houdini loading
                with hou.undos.disabler():
                    try:
                        comp_net = hou.node('/img/').createNode('img')
                        file_node = comp_net.createNode('file')
                        file_node.parm('filename1').set(icon_file_name)

                        # Todo: Support alpha channel
                        image_data = file_node.allPixelsAsString(depth=hou.imageDepth.Int8)
                        image = QImage(image_data, file_node.xRes(), file_node.yRes(), QImage.Format_RGB888)

                        self.icon_preview.setPixmap(QPixmap.fromImage(image).scaled(16, 16, Qt.KeepAspectRatio))
                    except hou.OperationFailed:
                        self.icon_preview.clear()
                    finally:
                        comp_net.destroy()
        else:
            try:
                icon = hou.qt.Icon(icon_file_name, 16, 16)
                self.icon_preview.setPixmap(icon.pixmap(16, 16))
            except hou.OperationFailed:
                self.icon_preview.clear()

    def _pickIconFromDisk(self):
        path = self.edit.text()
        if os.path.isdir(path):
            initial_dir = path
        elif os.path.isfile(path):
            initial_dir = os.path.dirname(path)
        else:
            initial_dir = os.path.dirname(hou.hipFile.path())
        icon_file_name, _ = QFileDialog.getOpenFileName(self, 'Pick Icon', initial_dir,
                                                        filter='Images (*.pic *.pic.Z *.picZ *.pic.gz *.picgz *.rat '
                                                               '*.tbf *.dsm *.picnc *.piclc *.rgb *.rgba *.sgi *.tif '
                                                               '*.tif3 *.tif16 *.tif32 *.tiff *.yuv *.pix *.als *.cin '
                                                               '*.kdk *.exr *.psd *.psb *.si *.tga *.vst *.vtg *.rla '
                                                               '*.rla16 *.rlb *.rlb16 *.hdr *.ptx *.ptex *.ies *.dds '
                                                               '*.qtl *.pic *.pic.Z *.pic.gz *.jpg *.jpeg *.bmp *.png '
                                                               '*.svg *.);;'
                                                               'All (*.*)')
        if icon_file_name:
            self.edit.setText(icon_file_name)

    def _pickIconFromHoudini(self):
        icon_file_name = FindIconDialog.getIconName(self, 'Pick Icon', self.edit.text())
        if icon_file_name:
            self.edit.setText(icon_file_name.replace('.svg', ''))


class LocationField(QWidget):
    def __init__(self, content=''):
        super(LocationField, self).__init__()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.edit = QLineEdit(content)
        layout.addWidget(self.edit)

        self.pick_location_button = QPushButton()
        self.pick_location_button.setToolTip('Pick location')
        self.pick_location_button.setFixedSize(24, 24)
        self.pick_location_button.setIcon(hou.qt.Icon('BUTTONS_chooser_folder', 16, 16))
        self.pick_location_button.clicked.connect(self._pickLocation)
        layout.addWidget(self.pick_location_button)

    def text(self):
        return self.edit.text()

    def path(self):
        return hou.expandString(self.edit.text())

    def _pickLocation(self):
        path = QFileDialog.getExistingDirectory(self, 'Pick Location', self.path())
        if path:
            path = hou.text.collapseCommonVars(path, ['$HOUDINI_USER_PREF_DIR', '$HIP', '$JOB'])
            self.edit.setText(path)


class MakeHDAByTemplateDialog(QDialog):
    def __init__(self, node, parent=None):
        super(MakeHDAByTemplateDialog, self).__init__(parent)

        # Data
        self.node = node

        self.setWindowTitle('TDK: HDA by Template')
        self.setWindowIcon(hou.qt.Icon('NODEFLAGS_template', 32, 32))
        self.resize(400, 250)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(4)
        main_layout.addLayout(form_layout)

        self.location_field = LocationField('$HOUDINI_USER_PREF_DIR/otls')
        form_layout.addRow('Location', self.location_field)

        self.label_field = QLineEdit()
        self.label_field.textChanged.connect(self._onLabelChanged)
        form_layout.addRow('Label', self.label_field)

        self.name_field = QLineEdit()
        self.name_field.textChanged.connect(self._onNameChanged)
        form_layout.addRow('Name', self.name_field)

        self.author_field = QLineEdit()
        self.author_field.textChanged.connect(self._onAuthorChanged)
        form_layout.addRow('Author', self.author_field)

        self.sections = QLineEdit()
        self.sections.textChanged.connect(self._onSectionsChanged)
        form_layout.addRow('Sections', self.sections)

        self.icon_field = IconField()
        form_layout.addRow('Icon', self.icon_field)

        self.version_field = QLineEdit('1.0')
        form_layout.addRow('Version', self.version_field)

        self.inherit_subnetwork_toggle = QCheckBox('Inherit subnetwork')
        self.inherit_subnetwork_toggle.setChecked(True)
        form_layout.addWidget(self.inherit_subnetwork_toggle)

        self.install_toggle = QCheckBox('Install new HDA')
        self.install_toggle.setChecked(True)
        form_layout.addWidget(self.install_toggle)

        self.replace_node_toggle = QCheckBox('Replace template node')
        self.replace_node_toggle.setChecked(True)
        self.install_toggle.toggled.connect(self.replace_node_toggle.setEnabled)
        form_layout.addWidget(self.replace_node_toggle)

        self.open_type_properties_toggle = QCheckBox('Open type properties')
        self.open_type_properties_toggle.setChecked(True)
        self.install_toggle.toggled.connect(self.open_type_properties_toggle.setEnabled)
        form_layout.addWidget(self.open_type_properties_toggle)

        buttons_layout = QHBoxLayout()
        main_layout.addLayout(buttons_layout)

        spacer = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Ignored)
        buttons_layout.addSpacerItem(spacer)

        ok_button = QPushButton('OK')
        ok_button.clicked.connect(self._onOk)
        buttons_layout.addWidget(ok_button)

        cancel_button = QPushButton('Cancel')
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_button)

        self.__label_changed = False
        self.__name_changed = False
        self.__author_changed = False
        self.__sections_changed = False

        user_name = hou.userName()
        self.author_field.setText(user_name)
        self._onAuthorChanged(user_name)

    def _onLabelChanged(self, label):
        self.__label_changed = True
        if not self.__name_changed:
            self.name_field.blockSignals(True)
            self.name_field.setText(label.lower().replace(' ', '_'))
            self.name_field.blockSignals(False)

    def _onNameChanged(self, name):
        self.__name_changed = True
        if not self.__label_changed:
            self.label_field.blockSignals(True)
            self.label_field.setText(name.replace('_', ' ').title())
            self.label_field.blockSignals(False)

    def _onAuthorChanged(self, author):
        self.__author_changed = True
        if not self.__sections_changed:
            self.sections.blockSignals(True)
            self.sections.setText(author.replace('_', ' ').title())
            self.sections.blockSignals(False)

    def _onSectionsChanged(self, sections):
        self.__sections_changed = True
        if not self.__author_changed:
            self.author_field.blockSignals(True)
            if ',' in sections:
                section = sections.split(',')[0].strip()
            else:
                section = sections.strip()
            self.author_field.setText(section.replace('_', ' ').title())
            self.author_field.blockSignals(False)

    def _onOk(self):
        if self.node:
            definition = makeNewHDAFromTemplateNode(self.node,
                                                    self.label_field.text(),
                                                    self.name_field.text(),
                                                    self.author_field.text(),
                                                    self.icon_field.text(),
                                                    self.sections.text(),
                                                    self.version_field.text(),
                                                    self.location_field.path(),
                                                    self.inherit_subnetwork_toggle.isChecked())
            if self.install_toggle.isChecked():
                hou.hda.installFile(definition.libraryFilePath())
                if self.replace_node_toggle.isChecked():
                    self.node = self.node.changeNodeType(definition.nodeTypeName(),
                                                         keep_network_contents=False)
                if self.open_type_properties_toggle.isChecked():
                    if self.replace_node_toggle.isChecked():
                        hou.ui.openTypePropertiesDialog(self.node)
                    else:
                        hou.ui.openTypePropertiesDialog(definition.nodeType())
        self.accept()


def showMakeHDAByTemplateDialog(**kwargs):
    if 'node' in kwargs:
        nodes = kwargs['node'],
    else:
        nodes = hou.selectedNodes()
    if not nodes:
        notify('No node selected', hou.severityType.Error)
        return
    elif len(nodes) > 1:
        notify('Too much nodes selected', hou.severityType.Error)
        return
    elif not nodes[0].type().name().startswith('tdk::template'):
        notify('Node is not TDK Template', hou.severityType.Error)
        return
    window = MakeHDAByTemplateDialog(nodes[0], hou.qt.mainWindow())
    window.show()
