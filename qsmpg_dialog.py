# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QSMPGDialog
                                 A QGIS plugin
 New implementation of SMPG
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2023-09-23
        git sha              : $Format:%H$
        copyright            : (C) 2023 by Juan Pablo Diaz Lombana
        email                : email.not@defined.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os
import time
import json
import traceback

from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import (
    QDialog,
    QMessageBox,
    QFileDialog,
    QGroupBox,
    QPushButton,
    QLineEdit,
    QCheckBox,
    QComboBox,
    QRadioButton,
    QLabel,
)

from qgis.core import (
    QgsTask, 
    QgsTaskManager,
)

from .map_settings_dialog import MapSettingsDialog
from .year_selection_dialog import YearSelectionDialog
from .progress_dialog import ProgressDialog

from .qsmpgCore.parsers.CSVParser import parse_csv
from .qsmpgCore.structures import Dataset
from .qsmpgCore.utils import (
    Parameters, Properties, define_seasonal_dict, parse_timestamps, 
    get_properties_validated_year_list, get_default_parameters_from_properties,
    )
    
from .qsmpgCore.exporters.WebExporter import export_to_web_files
from .qsmpgCore.exporters.CSVExporter import export_to_csv_files
from .qsmpgCore.exporters.ImageExporter import export_to_image_files
from .qsmpgCore.exporters.ParameterExporter import export_parameters
from .qsmpgCore.exporters.QGISExporter import generate_layers_from_csv

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'qsmpg_dialog_base.ui'))

class QSMPGDialog(QDialog, FORM_CLASS):
    """Main Dialog of the plugin

    This is the main dialog of QSMPG. It allows users to select 
    their dataset and most parameters for processing the dataset. 
    It displays information about the dataset and provides 
    fields for users to input their preferred options.
    """
    def __init__(self, parent=None):
        """This is the constructor for the class.

        It initializes the GUI elements and sets up the connections between 
        them.
        """
        super(QSMPGDialog, self).__init__(parent)
        self.setupUi(self)

        # task manager object that executes the processing tasks in threads.
        self.task_manager = QgsTaskManager(self) 

        # child dialogs
        self.year_selection_dialog = YearSelectionDialog(self)
        self.progress_dialog = ProgressDialog(self)
        self.map_settings_dialog = MapSettingsDialog(self)

        # input group
        self.loadFileButton: QPushButton
        self.datasetInputLineEdit: QLineEdit
        self.importParametersButton: QPushButton
        self.importParametersLineEdit: QLineEdit
        
        # climatology group
        self.climatologyStartComboBox: QComboBox
        self.climatologyEndComboBox: QComboBox

        # season monitoring group
        self.crossYearsCheckBox: QCheckBox
        self.seasonStartComboBox: QComboBox
        self.seasonEndComboBox: QComboBox

        # year selection group
        self.customYearsRadioButton: QRadioButton
        self.similarYearsRadioButton: QRadioButton
        self.similarYearsComboBox: QComboBox
        self.usePearsonCheckBox: QCheckBox
        self.selectYearsButton: QPushButton

        # analysis group
        self.observedDataRadioButton: QRadioButton
        self.forecastRadioButton: QRadioButton

        # outputs group
        self.exportWebCheckBox: QCheckBox
        self.exportImagesCheckBox: QCheckBox
        self.exportStatsCheckBox: QCheckBox
        self.exportParametersCheckBox: QCheckBox
        self.mappingButton: QPushButton

        # information group
        self.datasetInfoLabel: QLabel

        self.processButton: QPushButton

        # output groupbox
        self.output_checkboxes = [
            self.exportStatsCheckBox,
            self.exportWebCheckBox,
            self.exportParametersCheckBox,
            self.exportImagesCheckBox,
        ]

        # signal connections
        self.mappingButton.clicked.connect(self.mapping_button_event)
        self.exportStatsCheckBox.stateChanged.connect(self.export_stats_cb_changed_event)

        self.crossYearsCheckBox.stateChanged.connect(self.cross_years_cb_changed_event)
        self.customYearsRadioButton.toggled.connect(self.year_selection_rb_event)
        self.similarYearsRadioButton.toggled.connect(self.year_selection_rb_event)
        self.selectYearsButton.clicked.connect(self.select_years_btn_event)

        self.loadFileButton.clicked.connect(self.load_file_btn_event)
        self.importParametersButton.clicked.connect(self.import_parameters_btn_event)
        self.processButton.clicked.connect(self.process_btn_event)

    def get_parameters_from_widgets(self):
        """Get parameters from widgets and return them as a dictionary."""
        selected_years = None
        if self.customYearsRadioButton.isChecked():
            selected_years = self.year_selection_dialog.selected_years
        else:
            selected_years = self.similarYearsComboBox.currentText()

        return {
            "climatology_start": self.climatologyStartComboBox.currentText(),
            "climatology_end": self.climatologyEndComboBox.currentText(),
            "season_start": self.seasonStartComboBox.currentText(),
            "season_end": self.seasonEndComboBox.currentText(),
            "cross_years": self.crossYearsCheckBox.isChecked(),
            "selected_years": selected_years,
            "is_forecast": self.forecastRadioButton.isChecked(),
            "use_pearson": self.usePearsonCheckBox.isChecked(),
            "output_web": self.exportWebCheckBox.isChecked(),
            "output_images": self.exportImagesCheckBox.isChecked(),
            "output_stats": self.exportStatsCheckBox.isChecked(),
            "output_parameters": self.exportParametersCheckBox.isChecked(),
            "mapping_attributes": self.map_settings_dialog.settings['selected_fields'],
        }

    def update_fields(self, parameters: Parameters):
        """Update the UI fields based on the given `parameters` object.

        This method enables the fields in the dialog when a dataset is loaded,
        then it updates the fields with the given `parameters` object's values.

        Args:
            parameters (Parameters): The Parameters object containing the 
                settings and values to be set.
        """
        self.crossYearsCheckBox.setChecked(parameters.cross_years)
        year_ids = get_properties_validated_year_list(self.dataset_properties, self.crossYearsCheckBox.isChecked())
        sub_season_ids = define_seasonal_dict(self.crossYearsCheckBox.isChecked())

        # update climatology
        self.climatologyStartComboBox.setEnabled(True)
        self.climatologyStartComboBox.clear()
        self.climatologyStartComboBox.addItems(year_ids)
        if parameters.climatology_start is None or parameters.climatology_start not in year_ids:
            self.climatologyStartComboBox.setCurrentText(year_ids[0])
        else:
            self.climatologyStartComboBox.setCurrentText(parameters.climatology_start)
        self.climatologyEndComboBox.setEnabled(True)
        self.climatologyEndComboBox.clear()
        self.climatologyEndComboBox.addItems(year_ids)
        if parameters.climatology_end is None or parameters.climatology_end not in year_ids:
            self.climatologyEndComboBox.setCurrentText(year_ids[-1])
        else:
            self.climatologyEndComboBox.setCurrentText(parameters.climatology_end)

        # update monitoring season
        self.seasonStartComboBox.setEnabled(True)
        self.seasonStartComboBox.clear()
        self.seasonStartComboBox.addItems(sub_season_ids)
        if parameters.season_start is None or parameters.season_start not in sub_season_ids:
            self.seasonStartComboBox.setCurrentText(sub_season_ids[0])
        else:
            self.seasonStartComboBox.setCurrentText(parameters.season_start)
        self.seasonEndComboBox.setEnabled(True)
        self.seasonEndComboBox.clear()
        self.seasonEndComboBox.addItems(sub_season_ids)
        if parameters.season_end is None or parameters.season_end not in sub_season_ids:
            self.seasonEndComboBox.setCurrentText(sub_season_ids[-1])
        else:
            self.seasonEndComboBox.setCurrentText(parameters.season_end)

        # enable other widgets
        self.importParametersLineEdit.setEnabled(True)
        self.importParametersButton.setEnabled(True)
        self.customYearsRadioButton.setEnabled(True)
        self.similarYearsRadioButton.setEnabled(True)
        self.crossYearsCheckBox.setEnabled(True)
        self.processButton.setEnabled(True)

        # update year selection
        # for custom years
        if isinstance(parameters.selected_years, list) or parameters.selected_years is None:
            self.customYearsRadioButton.setChecked(True)
            self.selectYearsButton.setEnabled(True)
            self.similarYearsComboBox.setEnabled(False)
            self.usePearsonCheckBox.setEnabled(False)
        self.year_selection_dialog.updateYearsList(year_ids)
        self.year_selection_dialog.selected_years = parameters.selected_years
        self.year_selection_dialog.update_selection()
        # for similar years
        self.similarYearsComboBox.clear()
        self.similarYearsComboBox.addItems([str(y) for y in range(1, self.dataset_properties.season_quantity+1)])
        if isinstance(parameters.selected_years, str):
            self.similarYearsRadioButton.setChecked(True)
            self.similarYearsComboBox.setEnabled(True)
            self.similarYearsComboBox.setCurrentText(parameters.selected_years)
            self.usePearsonCheckBox.setEnabled(True)
            self.selectYearsButton.setEnabled(False)
        self.usePearsonCheckBox.setChecked(parameters.use_pearson)

        # update analysis type
        self.observedDataRadioButton.setEnabled(True)
        self.forecastRadioButton.setEnabled(True)
        if parameters.is_forecast: self.forecastRadioButton.setChecked(True)
        else: self.observedDataRadioButton.setChecked(True)

        # update outputs
        self.exportWebCheckBox.setEnabled(True)
        self.exportWebCheckBox.setChecked(parameters.output_web)
        self.exportImagesCheckBox.setEnabled(True)
        self.exportImagesCheckBox.setChecked(parameters.output_images)
        self.exportStatsCheckBox.setEnabled(True)
        self.exportStatsCheckBox.setChecked(parameters.output_stats)
        self.exportParametersCheckBox.setEnabled(True)
        self.exportParametersCheckBox.setChecked(parameters.output_parameters)
        self.mappingButton.setEnabled(parameters.output_stats)
        self.map_settings_dialog.settings['selected_fields'] = parameters.mapping_attributes

    def load_file_btn_event(self): 
        """Event handler for `loadFileButton`, it loads the dataset file.
        
        This is an event handler for when the user clicks the "Load Rainfall 
        Dataset (.csv)" button. It reads the selected dataset from a file and 
        parses it to create a structured data object. It also updates the 
        dialog's fields with default values based on the selected dataset 
        properties.
        """
        # path reading
        temp_dataset_source = QFileDialog.getOpenFileName(self, 'Open dataset file', None, "CSV files (*.csv)")[0]
        if temp_dataset_source == "":
            QMessageBox.warning(self, "Warning", 
                                'No dataset was selected.', 
                                QMessageBox.Ok)
            return
        self.selected_source = temp_dataset_source
        self.dataset_source_path = os.path.normpath(os.path.dirname(self.selected_source))
        self.dataset_filename = ''.join(os.path.basename(self.selected_source).split('.')[:-1])

        # parse dataset
        try:
            self.parsed_dataset, self.col_names, has_duplicates = parse_csv(self.selected_source)
            self.dataset_properties = Properties(parse_timestamps(self.col_names))
        except Exception as e:
            QMessageBox.critical(self, "Error", f'The dataset could not be read.\n\n{str(e)}\n\n{traceback.format_exc()}', QMessageBox.Ok)
            return
        if has_duplicates:
            QMessageBox.warning(self, "Warning", 
                                'Duplicated place names have been found.\nThe program might produce unexpected results.', 
                                QMessageBox.Ok)

        # set form fields content from data
        self.datasetInputLineEdit.setText(self.selected_source)
        default_parameters = Parameters()
        default_parameters.set_parameters(
            get_default_parameters_from_properties(self.dataset_properties, ['selected_years'])
            )
        self.update_fields(default_parameters)
        self.year_selection_dialog.selected_years = self.dataset_properties.year_ids
        self.update_dialog_info(self.dataset_properties)

    def process_btn_event(self):
        """Event handler for `processButton`, it outputs the processed data.
        
        This is an event handler for when the user clicks the "Process" button. 
        It checks for any invalid input in the form and then performs 
        the computation of required data using the options given by the user. 
        It also displays a progress dialog while the tasks are being executed.
        """
        # invalid input handling
        if self.climatologyStartComboBox.currentIndex() > self.climatologyEndComboBox.currentIndex():
            QMessageBox.critical(self, "Error", 
                                 'The start of the climatology must be before the end of the climatology', 
                                 QMessageBox.Ok)
            return
        if self.seasonStartComboBox.currentIndex() > self.seasonEndComboBox.currentIndex():
            QMessageBox.critical(self, "Error", 
                                 'The start of the season must be before the end of the season.', 
                                 QMessageBox.Ok)
            return

        for output in self.output_checkboxes:
            if output.isChecked():
                break
        else:
            QMessageBox.warning(self, "Warning", 
                                'Please select at least one option from Output Preferences.', 
                                QMessageBox.Ok)
            return
        
        # path reading
        self.destination_path = os.path.normpath(QFileDialog.getExistingDirectory(self, 'Save results', self.dataset_source_path))
        if self.destination_path == ".":
            QMessageBox.warning(self, "Warning", 
                                'No export folder was selected.', 
                                QMessageBox.Ok)
            return
        
        # ask for creating subfolder
        dlg = QMessageBox.information(self, "Create new folder?", 
                            f'Do you want to create a folder for the report files?\nThe folder {self.dataset_filename} at the path {self.destination_path} will be created.', 
                            QMessageBox.Yes, QMessageBox.No)
        if dlg == QMessageBox.Yes:
            self.destination_path = os.path.join(self.destination_path, self.dataset_filename)
        
        # computation with parameters given from GUI
        parameters = Parameters(self.get_parameters_from_widgets())
        self.structured_dataset = Dataset(self.dataset_filename, self.parsed_dataset, self.col_names, parameters)
        
        # add selected output tasks to a list of tasks
        long_tasks: list[TaskHandler] = []
        if self.exportStatsCheckBox.isChecked():
            csv_task = TaskHandler('CSV Export Task', export_to_csv_files, self.destination_path, self.structured_dataset)
            long_tasks.append(csv_task)
            if not (self.map_settings_dialog.map_layer is None or 
                len(self.map_settings_dialog.settings['selected_fields']) == 0):
                map_task = TaskHandler(
                    'Summary Mapping Task',
                    generate_layers_from_csv, 
                    self.map_settings_dialog.settings,
                    self.map_settings_dialog.map_layer,
                    # the last argument will be passed by the LongTaskHandler after csv_task finishes
                )
                map_task.setDependentLayers([self.map_settings_dialog.map_layer])
                csv_task.addNextTask(map_task)
                long_tasks.append(map_task)

        if self.exportWebCheckBox.isChecked():
            long_tasks.append(TaskHandler(
                'Web Report Export Task', 
                export_to_web_files, 
                self.destination_path, 
                self.structured_dataset
            ))

        if self.exportParametersCheckBox.isChecked():
            long_tasks.append(TaskHandler(
                'Parameters Export Task', 
                export_parameters, 
                self.destination_path, 
                self.structured_dataset
                ))
            
        if self.exportImagesCheckBox.isChecked():
            long_tasks.append(TaskHandler(
                'Static Reports Export Task', 
                export_to_image_files, 
                self.destination_path, 
                self.structured_dataset
                ))

        self.progress_dialog.show()
        self.renderTime = time.perf_counter()
        # add tasks to task manager and run them
        for task in long_tasks:
            self.task_manager.addTask(task)

        # triggers event on progress dialog when finished
        self.task_manager.allTasksFinished.connect(lambda: self.progress_dialog.finish_wait(self.task_manager, long_tasks))

    def import_parameters_btn_event(self) -> None:
        """
        Event handler for `importParametersButton`, it loads a parameters file.

        This is an event handler for when the user clicks the 
        "Import Parameters" button. It reads the selected parameters from a 
        JSON file and updates the dialog's fields with those values.
        """
        # source selection
        temp_parameters_source = QFileDialog.getOpenFileName(self, 'Open parameters file', None, "JSON files (*.json)")[0]
        if temp_parameters_source == "": 
            QMessageBox.warning(self, "Warning", 
                                'No dataset was selected.', 
                                QMessageBox.Ok)
            return
        self.parameters_source = temp_parameters_source

        # file reading
        try:
            with open(self.parameters_source, 'r') as json_file:
                parameters = json.load(json_file)
            parameters = Parameters(parameters)
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Could not load parameters from {self.parameters_source}.\n\n{str(e)}\n\n{traceback.format_exc()}')
            return
        
        # field updates
        self.importParametersLineEdit.setText(self.parameters_source)
        self.update_fields(parameters)

    def cross_years_cb_changed_event(self):
        """Event handler for `crossYearsCheckBox`, it switches cross-years.

        This method is called whenever the "Cross-Year Seasons (July-June)" 
        checkbox changes state. 
        It updates the list of years available in the "Selected Years" combobox 
        based on whether or not the user has selected to cross years.
        """
        default_years = get_properties_validated_year_list(
            self.dataset_properties, self.crossYearsCheckBox.isChecked()
        )
        parameters = Parameters(
            {
                **self.get_parameters_from_widgets(),
                'climatology_start': None,
                'climatology_end': None,
                'season_start': None,
                'season_end': None,
                'selected_years': default_years,
                'cross_years': self.crossYearsCheckBox.isChecked(),
            }
        )
        self.update_fields(parameters)

    def year_selection_rb_event(self):
        """Event handler for year selection RadioButtons.
        
        This method is called whenever the user selects a radio button 
        indicating whether they want to select specific years or use similar 
        years. It enables or disables the appropriate fields in the dialog 
        based on their selection.
        """
        if self.customYearsRadioButton.isChecked():
            self.selectYearsButton.setEnabled(True)
            self.similarYearsComboBox.setEnabled(False)
            self.usePearsonCheckBox.setEnabled(False)
        elif self.similarYearsRadioButton.isChecked():
            self.similarYearsComboBox.setEnabled(True)
            self.usePearsonCheckBox.setEnabled(True)
            self.selectYearsButton.setEnabled(False)

    def export_stats_cb_changed_event(self):
        """Event handler for `exportStatsCheckBox`.
        
        It enables or disables the "Mapping Preferences" button 
        based on the state of the "Export Statistics" checkbox.
        """
        self.mappingButton.setEnabled(self.exportStatsCheckBox.isChecked())

    def select_years_btn_event(self):
        """Event handler for `selectYearsButton`.
        
        This is an event handler for when the user clicks the "Select Years" 
        button. It displays a dialog that allows the user to select specific 
        years from the dataset.
        """
        self.year_selection_dialog.show()

    def mapping_button_event(self):
        """Event handler for `mappingButton`.
        
        This method is called whenever the user selects the 
        "Mapping Preferences" button. It opens a new dialog that allows to 
        configure the generation of the maps.
        """
        self.map_settings_dialog.show()

    def update_dialog_info(self, dataset_properties: Properties):
        """Updates the label that contains information about the datset.
        
        This method updates the dataset information label with relevant 
        information about the selected dataset.

        Args:
            dataset_properties (Properties): Properties of the dataset
        """
        dg_text = \
f'''First Year: {dataset_properties.year_ids[0]}
Last Year: {dataset_properties.year_ids[-1]}
Current Year: {dataset_properties.current_season_id}
Dekads in Current Year: {dataset_properties.current_season_length}'''
        self.datasetInfoLabel.setText(dg_text)

class TaskHandler(QgsTask):
    """Class for handling tasks to be run in other threads.

    It provides an interface for handling tasks that will run in other threads.
    
    Attributes:
        fn (function): The function to be executed.
        args (list): The arguments to be passed to the function.
        kwargs (dict): The keyword arguments to be passed to the function.
        title (str): A string containing the title of the task.
        result: The result of the task, which is set in finished 
            after the task completes successfully.
        exception (Exception): An exception raised by the task if 
            it raises an exception during its execution.
        debug (bool): A flag indicating whether to print debug information or 
            not.
        time (int): The time elapsed since the task started.
    """
    def __init__(self, description, fn, *args, nextTask=None, dependentLayers=[], **kwargs):
        """
        Initializes the task handler with the given description, function, 
        arguments, and keyword arguments. It also sets up the next task 
        to be executed after this one is completed successfully.
        
        Args:
            description (str): A string describing the task.
            fn (function): The function to be executed.
            args (list): The arguments to be passed to the function.
            nextTask (TaskHandler): A task that will run after this task.
            dependantLayers (list[QgsVectorLayer]): A list of layers 
                that this task depends on.
            kwargs (dict): The keyword arguments to be passed to the function.
        """
        super().__init__(description, QgsTask.CanCancel)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.title = description
        self.result = None
        self.exception = None
        self.debug = False
        self.time = 0

        self.setDependentLayers(dependentLayers)
        self.nextTask = None
        if nextTask is not None:
            self.addNextTask(nextTask)

    def run(self):
        """Executes the function given to the task handler.

        Executes the given function with the given arguments and keyword 
        arguments. If the task is cancelled or raises an exception, it returns 
        False. Otherwise, it returns True.
        """
        if self.debug: print(f'{self.description()} started')
        if self.isCanceled():
            return False
        try:
            self.result = self.fn(*self.args)
            return True
        except Exception as e:
            self.exception = e
            return False

    def finished(self, result):
        """Called when the task is finished. 
        
        When the task finishes successfully, it sets the result of the task 
        to the return value of the function executed in `run`, and updates 
        the time elapsed since the task started. If there is a next task, 
        it adds the result of this task as an argument to the next task and 
        starts it. When the task finishes unsuccessfully (with an exception or 
        by cancelling), it sets the exception of the task to the exception 
        (if any) raised by the function and cancels the next task (if any).

        Args:
            result (bool): if the function completes successfully or not.
        """
        # when task completed successfully
        if result:
            ...
            if self.nextTask is not None:
                self.nextTask.args =  (*self.nextTask.args, self.result)
            self.time = self.elapsedTime()
            if self.debug: print(f'{self.description()} completed')
            return
        # when task did not complete successfully
        if self.exception is not None:
            if self.debug: print(f'{self.description()} raised an exeception')
            if self.nextTask is not None:
                self.nextTask.cancel()
                self.nextTask.unhold()
            return
        if self.debug: print(f'{self.description()} terminated')

    def cancel(self):
        """Called when the task is cancelled. 

        It cancels the next task and then calls the parent class's `cancel` 
        method.
        """
        if self.debug: print(f'{self.description()} got cancelled')
        if self.nextTask is not None:
            self.nextTask.cancel()
            self.nextTask.unhold()

        super().cancel()

    def addNextTask(self, task: QgsTask):
        """
        Adds a new task to be executed after this one completes successfully. 
        The new task is held until it is started by the `finished` method.

        Args:
            task (QgsTask): the task to be executed after this one is 
                completed.
        """
        self.nextTask = task
        task.hold()
        super().taskCompleted.connect(task.unhold)