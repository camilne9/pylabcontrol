from src.core import Parameter, Script
from PySide.QtCore import Signal, QThread
from src.instruments import PiezoController
from src.scripts import GalvoScan
import numpy as np
import scipy as sp

class AutoFocus(Script, QThread):
    """
Autofocus: WRITE SOME TEXT HERE
    """

    # NOTE THAT THE ORDER OF Script and QThread IS IMPORTANT!!
    _DEFAULT_SETTINGS = Parameter([
        Parameter('path', 'Z:/Lab/Cantilever/Measurements/----data_tmp_default----', str, 'path for data'),
        Parameter('tag', 'dummy_tag', str, 'tag for data'),
        Parameter('save', True, bool, 'save data on/off'),
        Parameter('piezo_min_voltage', 30.0, float, 'lower bound of piezo voltage sweep'),
        Parameter('piezo_max_voltage', 70.0, float, 'upper bound of piezo voltage sweep'),
        Parameter('num_sweep_points', 10, int, 'number of values to sweep between min and max voltage'),
        Parameter('mode', 'standard_deviation', ['mean', 'standard_deviation'], 'optimization function for focusing'),
        Parameter('wait_time', 0.1, float)
    ])

    _INSTRUMENTS = {
        'z_piezo': PiezoController
    }
    _SCRIPTS = {
        'take_image': GalvoScan
    }

    #This is the signal that will be emitted during the processing.
    #By including int as an argument, it lets the signal know to expect
    #an integer argument when emitting.
    updateProgress = Signal(float)
    def __init__(self, instruments, scripts, name = None, settings = None, log_output = None):
        """
        Example of a script that emits a QT signal for the gui
        Args:
            name (optional): name of script, if empty same as class name
            settings (optional): settings for this script, if empty same as default settings
        """
        Script.__init__(self, name, settings, instruments, scripts, log_output = log_output)
        # QtCore.QThread.__init__(self)
        QThread.__init__(self)


    def _function(self):
        """
        This is the actual function that will be executed. It uses only information that is provided in the settings property
        will be overwritten in the __init__
        """

        assert self.settings['piezo_min_voltage'] < self.settings['piezo_max_voltage'], 'Min voltage must be less than max!'

        z_piezo = self.instruments['z_piezo']['instance']
        z_piezo.update(self.instruments['z_piezo']['settings'])

        print('updated')

        sweep_voltages = np.linspace(self.settings['piezo_min_voltage'],
                                     self.settings['piezo_max_voltage'],
                                     self.settings['num_sweep_points'])

        self.data['sweep_voltages'] = sweep_voltages
        self.data['focus_function_result'] = []
        self.data['images'] = []

        for voltage in sweep_voltages:

            print('voltage', voltage)

            # set the voltage on the piezo
            z_piezo.voltage = float(voltage)
            self.log('Voltage set to {:f}'.format(voltage))

            # take a galvo scan
            self.scripts['take_image'].run()
            self.data['images'].append(self.scripts['take_image'].data['image_data'])
            self.log('Took image.')

            # calculate focusing function for this sweep
            if self.settings['mode'] == 'mean':
                self.data['focus_function_result'].append(float(np.mean(self.data['images'][-1])))
            elif self.settings['mode'] == 'std_dev':
                self.data['focus_function_result'].append(float(np.std(self.data['images'][-1])))

            # update progress bar
            progress = 100.0 * np.where(sweep_voltages == voltage)[0] / float(self.settings['num_sweep_points'])
            self.updateProgress.emit(progress)

        # fit the data and set piezo to focus spot
        gaussian = lambda x, noise, amp, center, width: \
            noise + amp * np.exp(((x-center)**2/(2*(width)**2)))
        center_guess = (self.data['sweep_voltages'][-1] - self.data['sweep_voltages'][0])/2 + self.data['sweep_voltages'][0]
        width_guess = 10.0
        noise_guess = np.min(self.data['sweep_voltages'])
        amplitude_guess = np.max(self.data['sweep_voltages']) - noise_guess

        reasonable_params = [noise_guess, amplitude_guess, width_guess, center_guess]

        p2, success = sp.optimize.curve_fit(gaussian, self.data['sweep_voltages'],
                                            self.data['focus_function_result'], reasonable_params)

        self.data['focusing_fit_parameters'] = {}
        if success:
            self.log('Fit succeeded.')
            self.data['focusing_fit_parameters']['background_noise'] = p2[0]
            self.data['focusing_fit_parameters']['amplitude'] = p2[1]
            self.data['focusing_fit_parameters']['center'] = p2[2]
            self.data['focusing_fit_parameters']['width'] = p2[3]
        else:
            self.log('Fit failed.')
            self.data['focusing_fit_parameters']['background_noise'] = 0.0
            self.data['focusing_fit_parameters']['amplitude'] = 0.0
            self.data['focusing_fit_parameters']['center'] = 0.0
            self.data['focusing_fit_parameters']['width'] = 0.0

        # check to see if data should be saved and save it
        if self.settings.save:
            self.log('Saving...')
            self.save()
            self.save_data()
            self.save_log()
            self.log('Finished saving.')


    def plot(self, axes):

        # plot current focusing data
        axes.plot(self.data['sweep_voltages'][0:len(self.data['focus_function_result'])],
                  self.data['focus_function_result'])

        # plot best fit
        if 'focusing_fit_parameters' in self.data and self.data['focusing_fit_parameters']['background_noise'] != 0.0:
            gaussian = lambda x, params: params[0] + params[1] * np.exp(((x - params[2]) ** 2 / (2 * params[3]) ** 2))
            parameters = [self.data['focusing_fit_parameters']['background_noise'],
                          self.data['focusing_fit_parameters']['amplitude'],
                          self.data['focusing_fit_parameters']['center'],
                          self.data['focusing_fit_parameters']['width']]

            fit = [gaussian(x, parameters) for x in self.data['sweep_voltages']]
            axes.plot(self.data['sweep_voltages'], fit)

        # format plot
        axes.set_xlim([self.data['sweep_voltages'][0], self.data['sweep_voltages'][-1]])
        axes.set_xlabel('Piezo Voltage [V]')
        axes.set_ylabel('Focusing Function')
        axes.set_title('Autofocusing Routine')


    def stop(self):
        self._abort = True


if __name__ == '__main__':
    # from src.core import Instrument
    # from src.scripts import GalvoScan
    # # instruments, loaded_failed = Instrument.load_and_append({'daq': 'DAQ'})
    # # print(instruments)
    # # gs = GalvoScan(instruments)
    #
    # scripts, loaded_failed, instruments = Script.load_and_append({"take_image": 'GalvoScan'})
    # print(scripts, instruments)
    # if loaded_failed != []:
    #     print('FAILED')
    #
    # instruments, loaded_failed = Instrument.load_and_append({'z_piezo':'PiezoController'},instruments)
    # print('DD', scripts, instruments)
    # if loaded_failed != []:
    #     print('FAILED')
    #
    # #
    # af = AutoFocus(name = 'aff', instruments=instruments, scripts=scripts)
    # print(af)
    scripts, loaded_failed, instruments = Script.load_and_append({"af": 'AutoFocus'})
    print(scripts, loaded_failed, instruments)