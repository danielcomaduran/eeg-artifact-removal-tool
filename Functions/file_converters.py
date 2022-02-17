""""

File converters
---------------
Set of functions to convert different file types:
- mat_to_npz
- edf_to_npz

"""

#%% Import libraries
import os
import mne
import numpy as np
import pandas as pd
from scipy import signal
from scipy.io import loadmat

#%% mat_to_npz
def mat_to_npz(file, save_file=False, save_loc='Data\\Imported', save_name=''):
    """
    Import a .mat file and convert to a .npz file. Meant to be used with the BETA dataset.

    Parameters
    ----------
        file: str
            Absolute path of the file to be imported
        save_file: bool, optional
            Boolean to save the data
        save_loc: str, optional
            Relative path of the saved data. Only necessary if save_file == True 
        save_name: str, optional
            Name of the data file to be saved. Only necessary if save_file == True

    Returns
    -------
        npz: list
            List with the same variables as the .npz file    

    Notes
    -----
    The .npz file is organized as follows:
        - EEG: samples x channels x frequencies [V]
        - srate: sampling rate [Hz]
        - ssvep: SSVEP stimulus frequencies [Hz]
        - chans: EEG channels  with columns [loc_x, loc_y, loc_z, channel_name]
    """

    # Settings
    ssvep_freqs = [10,12,15]    # SSVEP frequencies to extract

    # Load and separate data
    mat_data = loadmat(file, simplify_cells=True)   
    eeg_data = mat_data['data']['EEG']          # EEG data [channels x samples x block x ssvep_freqs] [uV]
    sup_data = mat_data['data']['suppl_info']   # Sumplementary information
    srate = sup_data['srate']       # Data sampling rate [Hz]   
    stim_freqs = sup_data['freqs']  # Stimulation frequencies [Hz]
    chans = sup_data['chan']        # Channel information [x,y,z,name]

    # Select trial to keep. There are a total of 4 trials
    trial = 1
    sel_freqs = np.isin(stim_freqs, ssvep_freqs)                # Search for index of selected frequencies
    trim_data = eeg_data[:,:,trial, sel_freqs].swapaxes(0,1)    # Output data. [samples x channels x frequencies] [uV]
    scaled_data = trim_data * 1e-6  # Data scaled to [V]

    # Save data to .npz file
    if save_file:
        # Determine parent directory
        par_dir = os.getcwd()

        # Check if save_loc exist. If it doesn't exist, create it        
        if os.path.isdir(os.path.join(par_dir, save_loc)):
            pass
        else:
            os.mkdir(os.path.join(par_dir, save_loc))

        # Save data
        temp_file_name = save_loc+'\\'+save_name
        np.savez(temp_file_name, eeg=scaled_data, srate=srate, ssvep=ssvep_freqs, chans=chans)

    # Organize data for output 
    npz = [scaled_data, srate, ssvep_freqs, chans]

    return npz

#%% edf_to_npz
def edf_to_npz(eeg_file, labels_file, save_file=False, save_loc='Data\\Imported', save_name=''):
    """
    Import an .edf file and convert it to an .npz file. Meant to be used with the Temple University dataset

    Parameters
    ----------
        eeg_file: str
            Absolute path of the .edf file to be imported. Does not need the file extension
        labels_file: str
            Absolute path of the .csv file to be imported. Does not need the file extension
        save_file: bool, optional
            Boolean to save the data
        save_loc: str, optional
            Relative path of the saved data. Only necessary if save_file == True 
        save_name: str, optional
            Name of the data file to be saved. Only necessary if save_file == True

    Returns
    -------
        npz: list
            List with the same variables as the .npz file   

    Notes
    -----
    The .npz file is organized as follows:
        - eye_eeg: list
            Eye artifact EEG. Each value in the list is an array of samples x channels [V].
            A list is used because every artifact has a different duration
        - mus_eeg: list
            Muscle artifact EEG. Each value in the list is an array of samples x channels [V]. 
            A list is used because every artifact has a different duration
        - srate: int
            Sampling rate [Hz]
        - chans: EEG channels  with columns [loc_x, loc_y, loc_z, channel_name]
    
    The Temple University data is sampled at 400 Hz. The function returns data downsampled 
    to 250 Hz, to match the sampling rat eof the BETA dataset. 

    """
    # Check if eeg_file and labels_file have the name extension included
    if not eeg_file[-4:] == '.edf':   
        eeg_file = eeg_file + '.edf'
    if not labels_file[-4:] == '.csv':
        labels_file = labels_file + '.csv'

    # Import EEG data
    edf_data = mne.io.read_raw_edf(eeg_file)
    eeg = edf_data.get_data()  # EEG [V]

    # - Transpose EEG data to have channels as columns
    [a, b] = np.shape(eeg)
    if b > a:
        eeg = eeg.T

    # - Extra information
    srate = edf_data.info['sfreq']  # Data sampling rate [Hz]
    chans = edf_data.info.ch_names  # Channel information [name]
    for c in range(len(chans)):     # Eliminate extra characters in channel information
        t_chan = chans[c]
        t_chan = t_chan.replace('EEG ','')
        t_chan = t_chan.replace('-REF','')
        chans[c] = t_chan


    # Resample data to new sample rate
    new_srate = 250    # [Hz]

    # - Original data
    l_oeeg = len(eeg)   # Length of original EEG [n]
    eeg = signal.resample(eeg, int((l_oeeg*new_srate)/srate)) # Resampled data

    # - Resampled data
    l_neeg = len(eeg)   # Length of new EEG signal [n]
    time = np.linspace(0, l_neeg/new_srate, l_neeg)   # New time vector
    srate = new_srate # New sampling rate [Hz]


    # Artifact annotations
    full_artifact_notes = pd.read_csv(labels_file, header=4)
    file_key = eeg_file.split('\\')[-1].split('.')[0]   # Get only file name [str]
    sub_artifact_notes = full_artifact_notes[full_artifact_notes['# key'].isin([file_key])]    # Subset for current trial

    # - Separate eye and muscle artifacts
    eye_artifacts = sub_artifact_notes[sub_artifact_notes[' artifact_label'].isin(['eyem'])]
    mus_artifacts = sub_artifact_notes[sub_artifact_notes[' artifact_label'].isin(['musc'])]


    #%% Trim data to eye and muscle artifacts
    # - Trimmed data is stored in a list with each element being one artifact
    # - Each element is a np.array with dimensions = samples x channels

    # - Initialize lists
    eye_eeg = np.array([None] * eye_artifacts.shape[0], dtype='object')
    mus_eeg = np.array([None] * mus_artifacts.shape[0], dtype='object')

    # - Eye artifacts
    for eye in range(len(eye_artifacts)):
        [start_time, stop_time] = eye_artifacts.iloc[eye][[' start_time', ' stop_time']]
        eye_eeg[eye] = eeg[(time>=start_time)&(time<=stop_time), :]

    # - Muscle artifacts
    for mus in range(len(mus_artifacts)):
        [start_time, stop_time] = mus_artifacts.iloc[mus][[' start_time', ' stop_time']]
        mus_eeg[mus] = eeg[(time>=start_time)&(time<=stop_time), :]


    #%% Save .NPZ data files
    if save_file:
        # Determine parent directory
        par_dir = os.getcwd()

        # Check if save_loc exist. If it doesn't exist, create it        
        if os.path.isdir(os.path.join(par_dir, save_loc)):
            pass
        else:
            os.mkdir(os.path.join(par_dir, save_loc))

        # Save data
        output_file = save_loc+'\\'+save_name
        np.savez(output_file+'.npz', eye_eeg=eye_eeg, mus_eeg=mus_eeg, srate=srate, chans=chans)

    # Output npz variable
    npz = [eye_eeg, mus_eeg, srate, chans]

    return npz