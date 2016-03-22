
import sip
sip.setapi('QVariant', 2)# set to version to so that the gui returns QString objects and not generic QVariants
from PyQt4 import QtCore, QtGui
from src.core import Parameter, Instrument


def fill_tree(tree, parameters):
    """
    fills a tree with nested parameters
    Args:
        tree: QtGui.QTreeWidget
        parameters: dictionary or Parameter object

    Returns:

    """
    assert isinstance(parameters, (dict, Parameter))

    for key, value in parameters.iteritems():
        if isinstance(value, Parameter):
            B26QTreeItem(tree, key, value, parameters.valid_values[key], parameters.info[key])
        else:
            B26QTreeItem(tree, key, value, type(value), '')


class B26QTreeItem(QtGui.QTreeWidgetItem):
    '''
    Custom QTreeWidgetItem with Widgets
    '''

    def __init__(self, parent, name, value, valid_values, info, log = None, target = None, visible = True):
        """
        Args:
            parent:
            name:
            value:
            valid_values:
            info:
            log: log function if not provided, output is send to standard print command
            target (optional):
            visible (optional):

        Returns:

        """

        ## Init super class ( QtGui.QTreeWidgetItem )
        super(B26QTreeItem, self ).__init__( parent )

        self.name = name
        self.valid_values = valid_values
        self.value = value
        self.info = info
        self.target = target
        self.visible = visible

        # if no log function is provided define one
        if log is None:
            def log(txt):
                print(txt)
        self.log = log

        self.setData(0, 0, unicode(self.name))
        # self.setText(0, unicode(self.name))


        if isinstance(self.valid_values, list):
            self.combobox = QtGui.QComboBox()
            for item in self.valid_values:
                self.combobox.addItem(unicode(item))
            self.combobox.setCurrentIndex(self.combobox.findText(unicode(self.value)))
            self.treeWidget().setItemWidget( self, 1, self.combobox )
            self.combobox.currentIndexChanged.connect(lambda: self.setData(1, 2, self.combobox))

        elif self.valid_values is bool:
            self.check = QtGui.QCheckBox()
            self.check.setChecked(self.value)
            self.treeWidget().setItemWidget( self, 1, self.check )
            self.check.stateChanged.connect(lambda: self.setData(1, 2, self.check))

        elif isinstance(self.value, Parameter):
            for key, value in self.value.iteritems():
                B26QTreeItem(self, key, value, self.valid_values[key], self.info[key], target=self.target, visible=self.visible)

        elif isinstance(self.value, dict):
            for key, value in self.value.iteritems():
                B26QTreeItem(self, key, value, type(value), '', target=self.target, visible=self.visible)

        elif isinstance(self.value, Instrument):
            for key, value in self.value.parameters.iteritems():
                B26QTreeItem(self, key, value, self.value.parameters.valid_values[key], self.value.parameters.info[key], target=self.value, visible=self.visible)
        else:
            self.setText(1, unicode(self.value))
            self.setFlags(self.flags() | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsDragEnabled | QtCore.Qt.ItemIsEditable)
        self.setToolTip(1, unicode(self.info  if isinstance(self.info, str) else ''))

    @property
    def value(self):
        return self._value
    @value.setter
    def value(self, value):
        if Parameter.is_valid(value, self.valid_values):
            self._value = value
        else:
            raise TypeError("wrong type {:s}, expected {:s}".format(str(value), str(self.valid_values)))

    @property
    def visible(self):
        return self._visible
    @visible.setter
    def visible(self, value):
        assert isinstance(value, bool)
        self._visible = value

    def setData(self, column, role, value):
        assert isinstance(column, int)
        assert isinstance(role, int)

        msg = None


        # if role = 2 (editrole, value has been entered)
        if role == 2 and column == 1:
            if isinstance(value, QtCore.QString):
                if not isinstance(self.valid_values, list):
                    value = self.cast_type(value) # cast into same type as valid values
            elif isinstance(value, QtGui.QComboBox):
                value = value.currentText()
            elif isinstance(value, QtGui.QCheckBox):
                value = int(value.checkState()) # this gives 2 (True) and 0 (False)
                value = value == 2
            # save value in internal variable
            self.value = value

        elif column == 0:
            # labels should not be changed so we set it back
            value = self.name
            msg = 'labels can not be changed, label {:s} reset'.format(str(value))

        if value == None:
            value = self.value
            msg = 'value not valid, reset to {:s}'.format(str(value))

        # if msg is not None:
        #     self.log(msg)

        super(B26QTreeItem, self).setData(column, role, value)

    def cast_type(self, var, typ = None):
        """
        cast the value into the type typ
        if typ is not provided it is set to self.valid_values
        Args:
            var: variable to be cast
            typ: target type

        Returns: the variable var csat into type typ

        """

        if typ is None:
            typ = self.valid_values

        try:
            if typ == int:
                var = int(var)
            elif typ == float:
                var = float(var)
            elif typ  == str:
                var = str(var)
            else:
                var = None
        except ValueError:
            var = None
        return var


    def get_instrument(self):
        """

        Returns: the instrument and the path to the instrument to which this item belongs

        """
        # todo: test this function, if it works, we can remove the propertie self.target
        parent = self.parent()

        if isinstance(self.value, Instrument):
            instrument = self.value
            path_to_instrument = []
        else:
            instrument = None
            path_to_instrument = [self.name]
            while parent is not None:
                print('hhh', parent.value)
                if isinstance(parent.value, Instrument):
                    instrument = parent.value
                    parent = None
                else:
                    path_to_instrument.append(parent.name)
                    parent = parent.parent()

        path_to_instrument.reverse()
        return instrument, path_to_instrument

