from matplotlib.pyplot import axis
import pandas as pd
import numpy as np
import os
import pickle
import obspy
from subprocess import call
import json
import datetime
from scipy.spatial import distance
from scipy.spatial import distance_matrix
import matplotlib.pyplot as plt



class PhaseNet_Analysis (object):

    '''
    This class analysis and compare the 'P' picks and 'S' Picks
    with the given catalog.
    '''

    def __init__(self,phasenet_direc: 'str', chile_GFZ_online_direc:'str', export_DF_path:'str',
                export_mseed_path:'str', working_direc:'str', picks_name:'str',
                start_year_analysis:'int', start_day_analysis:'int', 
                end_year_analysis:'int', end_day_analysis:'int', analysis:'bool'):

        '''
        Parameters initialization:
            - phasenet_direc: The path of PhaseNet package

            - chile_GFZ_online_direc: The directory of stored all three components mseed files.

            - export_DF_path : The path of all mseed files DataFrame.
                                This directory must contain 'DF_chile_path_file.pkl'.
                                This DataFrame is created once using "generate_DF_file_path" function.
                                This function is not used often.
                                After run "DF_path" function, another two DataFrames
                                ("DF_selected_chile_path_file.pkl" and "DF_auxiliary_path_file.pkl") 
                                will be created and stored in this directory as a feed path to run PhaseNet.

                                It should be noted that after running "events_data_frame", "events.pkl" will be created
                                and stored in this directory.

            - export_mseed_path: The folder path of writing three components mseed.
                This folder will be used by PhaseNet.

            - working_direc: the path of working directory

            - picks_name: the name of picks Dataframe existed in 'export_DF_path ' directory

            - start_year_analysis: start year of analysis with 4 digit (like 2011)

            - start_day_analysis: start day of analysis related to 
                                the start_year_analysis. This variable should between 1 to 365. 

            - end_year_analysis: end year of analysis with 4 digit (like 2011)

            - end_day_analysis: end day of analysis related to 
                                the end_year_analysis. This variable should between 1 to 365. 

            - analysis (boolean): Because running PhaseNet is time consumming, analysis variable helps to use existing 
                "PhaseNet_result_s_picks.pkl", "PhaseNet_result_s_picks.pkl" which are generated by Phasenet without running PhaseNet again.
                
                If you want to run PhaseNet for the first time in the given interval, this variable should be set to True
                If you already have "PhaseNet_result_s_picks.pkl", "PhaseNet_result_s_picks.pkl" for the given interval, this variable should be set to False.
                                
                                - True: start running PhaseNet and perform visualization.
                                - False:  Use existing PhaseNet results and perform visualization.

            
            - time_lag_threshold (int) : Proper time lag threshold in millisecond.
                                        This variable has been use to perform qaulity control of PhaseNet and existing catalog.

        '''
        os.chdir('{0}'.format(phasenet_direc))
        self.PROJECT_ROOT = os.getcwd()

        self.chile_GFZ_online_direc = chile_GFZ_online_direc
        self.export_DF_path = export_DF_path
        self.export_mseed_path = export_mseed_path
        self.working_direc = working_direc
        self.picks_name = picks_name
        self.start_year_analysis = start_year_analysis
        self.start_day_analysis = start_day_analysis
        self.end_year_analysis = end_year_analysis
        self.end_day_analysis = end_day_analysis
        self.analysis = analysis
        self.time_lag_threshold = time_lag_threshold
    
    def __call__ (self):


        # load "DF_auxiliary_path_file.pkl" and "DF_selected_chile_path_file.pkl" based on the
        # given interval.

        if self.analysis == True:

            self.DF_path ()

            # load DF_auxiliary_path_file.pkl
            with open(os.path.join(self.export_DF_path, "DF_auxiliary_path_file.pkl"),'rb') as fp:
                DF_auxiliary_path_file = pickle.load(fp)

            # load DF_selected_chile_path_file.pkl
            with open(os.path.join(self.export_DF_path, "DF_selected_chile_path_file.pkl"),'rb') as fp:
                DF_selected_chile_path_file = pickle.load(fp)
            

            # Creat S picks DataFrame
            df_S_picks = pd.DataFrame(index =[])

            # Creat P picks DataFrame
            df_P_picks = pd.DataFrame(index =[])


            # Iterate over all mseed files which contains 3 components .
            
            for i in range (DF_auxiliary_path_file.shape[0]):

                # Write mseed file to mseed folder path
                mseed_name = self.three_components_mseed_maker (i,DF_auxiliary_path_file, 
                                        DF_selected_chile_path_file)
                
                # Write the name of mseed file in mseed.csv
                self.write_mseed_names(mseed_name)

                # Run PhaseNet
                self.run_phasenet()

                # Remove created mseed in mseed folder to free up memory
                self.remove_mseed (mseed_name)

                # Read the output of PhaseNet and store P picks and S picks in two data frames
                p_picks, s_picks = self.read_picks()

                # save data in data frame
                #df_total = self.save_DF (df_p_picks, df_s_picks, mseed_name, df_picks)
                #df_picks = df_total
                df_S_picks = pd.concat([df_S_picks, s_picks], axis=0)
                df_P_picks = pd.concat([df_P_picks, p_picks], axis=0)

            # save PhaseNet p picks result file in the export directory as 'PhaseNet_result_p_picks.pkl'
            df_P_picks.to_pickle(os.path.join(self.export_DF_path, 'PhaseNet_result_p_picks.pkl'))

            # save PhaseNet s picks result file in the export directory as 'PhaseNet_result_s_picks.pkl'
            df_S_picks.to_pickle(os.path.join(self.export_DF_path, 'PhaseNet_result_s_picks.pkl'))

            # Apply filter on catalog data between start time and end time of analysis
            catalog_DF_P_picks, catalog_DF_S_picks = self.filter_picks_DF ()

            # save catalog p picks result file in the export directory as 'catalog_p_picks.pkl'
            catalog_DF_P_picks.to_pickle(os.path.join(self.export_DF_path, 'catalog_p_picks.pkl'))

            # save PhaseNet s picks result file in the export directory as 'catalog_s_picks.pkl'
            catalog_DF_S_picks.to_pickle(os.path.join(self.export_DF_path, 'catalog_s_picks.pkl'))

            # Perform visulization & qaulity control of P picks
            # The results of visulization will be found at self.export_DF_path directory
            self.compare_PhaseNet_catalog_P_picks()

            # Perform visulization & qaulity control of S picks
            # The results of visulization will be found at self.export_DF_path directory
            self.compare_PhaseNet_catalog_S_picks()
        

        # Perform visulization without running PhaseNet
        else:

            # Perform visulization & qaulity control of P picks
            # The results of visulization will be found at self.export_DF_path directory
            self.compare_PhaseNet_catalog_P_picks()

            # Perform visulization & qaulity control of S picks
            # The results of visulization will be found at self.export_DF_path directory
            self.compare_PhaseNet_catalog_S_picks()      
   
    
    def DF_path (self):

        '''
        This function loads "DF_chile_path_file.pkl" file (path of all mseed files
        from export_DF_path and filter the data between the given interval.
        After using this function, 'DF_selected_chile_path_file.pkl' and 
        'DF_auxiliary_path_file.pkl' will be created to feed data to PhaseNet.

        Important note: This function will not consider mseed file with less than 3- components.
        '''

        # Read pickle data (Path of all chile stream data)
        with open(os.path.join(self.export_DF_path, "DF_chile_path_file.pkl"),'rb') as fp:
            chile_path_file = pickle.load(fp)

        chile_path_file = chile_path_file[(chile_path_file['year']>= self.start_year_analysis) & 
                    (chile_path_file['year']<= self.end_year_analysis)]

        chile_path_file['convert_yeartoday']= 365*chile_path_file['year']+chile_path_file['day']
        
        # creat upper and lower limit to filter
        lower_limit = 365*self.start_year_analysis + self.start_day_analysis 
        upper_limit = 365*self.end_year_analysis   + self.end_day_analysis

        # Apply filter
        chile_path_file = chile_path_file[(chile_path_file['convert_yeartoday']>= lower_limit) & 
                (chile_path_file['convert_yeartoday']<= upper_limit)]   

        chile_path_file = chile_path_file.drop_duplicates()

        # creat new DataFrame to make sure all 3-components are existed
        df_counter = chile_path_file.groupby(['network','station', 'year', 'day']).size().reset_index(name='count')
        df_counter = df_counter[df_counter['count']==3]

        # drop the 'count' column
        df_counter = df_counter.drop(columns=['count'])

        # Save selected DataFrame based on given time interval
        chile_path_file.to_pickle(os.path.join(self.export_DF_path , 'DF_selected_chile_path_file.pkl'))

        # Save auxiliary DataFrame based on given time interval
        df_counter.to_pickle(os.path.join(self.export_DF_path , 'DF_auxiliary_path_file.pkl'))

    
    def three_components_mseed_maker (self,i:'int',DF_auxiliary_path_file, 
                                    DF_selected_chile_path_file):
        '''
        This function write a single three components mseed file in mseed folder.
        Parameters:
                    - i (int): the ith row of "DF_auxiliary_path_file" data frame
                    - DF_auxiliary_path_file (data frame): A data frame containing mseed file name 
                        with existed three componets.
                    - DF_selected_chile_path_file(data frame): A selected data frame based on the given time interval.
                    
        '''



        # Apply filter to determine the three components in "DF_selected_chile_path_file"
        df = DF_selected_chile_path_file[['network', 'station', 'year','day']]==DF_auxiliary_path_file.iloc[i]
        df_components = DF_selected_chile_path_file[(df['network']== True) & 
                        (df['station']== True) & (df['year']== True) &
                        (df['day']== True)]

        # Read three components mseed file 
        streamZ = obspy.read(df_components.path.iloc[2])
        streamN = obspy.read(df_components.path.iloc[1])
        streamE = obspy.read(df_components.path.iloc[0])
        streamN += streamE
        streamN += streamZ
        stream = streamN.sort()

        # Write the mseed file (three components) in mseed folder
        string = df_components.file_name.iloc[2]
        mseed_name = string.replace("HHE", "").replace("HHN", "").replace("HHZ", "")
        stream.write(os.path.join(self.export_mseed_path, mseed_name), sep="\t", format="MSEED")

        return mseed_name

    def write_mseed_names(self, mseed_name):
        '''
        This function write the name of mseed file to mseed.csv.
        This mseed.csv will be used by PhaseNet
        '''
        df = pd.DataFrame ([mseed_name], columns = ['fname'])

        df.to_csv((os.path.join(self.working_direc, 'mseed.csv')),index=False)
    
    def run_phasenet (self):
        '''
        Run the predefined PhaseNet model (model/190703-214543) to pick S and P waves.
        '''
        #cmd = '/home/javak/miniconda3/envs/phasenet/bin/python phasenet/predict.py --model=model/190703-214543 --data_list=/home/javak/Sample_data_chile/mseed.csv --data_dir=/home/javak/Sample_data_chile/mseed --format=mseed --plot_figure'.split()
        cmd = '/home/javak/miniconda3/envs/phasenet/bin/python phasenet/predict.py --model=model/190703-214543 --data_list=/home/javak/Sample_data_chile/mseed.csv --data_dir=/home/javak/Sample_data_chile/mseed --format=mseed'.split()
        
        call(cmd)
    
    def read_picks (self):

        '''
        Read the csv file of PhaseNet output and return the P picks and S picks.
        '''
        picks_csv = pd.read_csv(os.path.join(self.PROJECT_ROOT, "results/picks.csv"), sep="\t")
        picks_csv.loc[:, 'p_idx'] = picks_csv["p_idx"].apply(lambda x: x.strip("[]").split(","))
        picks_csv.loc[:, 'p_prob'] = picks_csv["p_prob"].apply(lambda x: x.strip("[]").split(","))
        picks_csv.loc[:, 's_idx'] = picks_csv["s_idx"].apply(lambda x: x.strip("[]").split(","))
        picks_csv.loc[:, 's_prob'] = picks_csv["s_prob"].apply(lambda x: x.strip("[]").split(","))

        with open(os.path.join(self.PROJECT_ROOT, "results/picks.json")) as fp:
            picks_json = json.load(fp)
        
        df = pd.DataFrame.from_dict(pd.json_normalize(picks_json), orient='columns')
        df_p_picks = df[df["type"] == 'p']
        df_s_picks = df[df["type"] == 's']

        return df_p_picks, df_s_picks
    
    def remove_mseed (self,mseed_name):

        '''
        This function removes created mseed in mseed folder to free up memory.
        '''

        file_path = os.path.join(self.export_mseed_path, mseed_name)
        os.remove(file_path)
    
    def save_DF (self, df_p_waves, df_s_waves, daily_data, df):

        data = {'P_waves':[df_p_waves],
                'S_waves':[df_s_waves]
                }

        # Creates pandas DataFrame.
        df_new = pd.DataFrame(data, index =[daily_data])
        df_total = df.append(df_new)
        return df_total
    
    def filter_picks_DF (self):

        '''
        This function apply filter on existing picks DataFrame according to 
        start_year_analysis, end_year_analysis, start_day_analysis, end_day_analysis.
        '''
        # load picks_2007_2020.pkl
        with open(os.path.join(self.export_DF_path, self.picks_name),'rb') as fp:
            DF_picks = pickle.load(fp)

        # convert the Day of Year in Python to Month/Day
        start_date = datetime.datetime.strptime('{} {}'.format(start_day_analysis, start_year_analysis),'%j %Y')
        end_date   = datetime.datetime.strptime('{} {}'.format(end_day_analysis, end_year_analysis),'%j %Y')

        start_date_obspy = obspy.UTCDateTime(year=start_year_analysis, month=start_date.month, day=start_date.day, strict=False)
        end_date_obspy = obspy.UTCDateTime(year=end_year_analysis, month=end_date.month, day=end_date.day, hour=24, strict=False)

 
        catalog_DF_P_picks = DF_picks[(DF_picks['picks_time']>= start_date_obspy) & (DF_picks['picks_time']<=end_date_obspy) & (DF_picks['phase_hint']=='P')]
        catalog_DF_S_picks = DF_picks[(DF_picks['picks_time']>= start_date_obspy) & (DF_picks['picks_time']<=end_date_obspy) & (DF_picks['phase_hint']=='S')]

        return catalog_DF_P_picks, catalog_DF_S_picks


    def compare_PhaseNet_catalog_P_picks (self):

        '''
        This function compares the result of PhaseNet and existing catalog.
        Parameters:
                    - catalog_DF_P_picks   (DataFrame): catalog P picks
                    - df_P_picks           (DataFrame): PhaseNet P picks
        '''
        
        # catalog_DF_P_picks, df_P_picks
        with open(os.path.join(self.export_DF_path, "PhaseNet_result_p_picks.pkl"),'rb') as fp:
            df_P_picks = pickle.load(fp)

        with open(os.path.join(self.export_DF_path, "catalog_p_picks.pkl"),'rb') as fp:
            catalog_DF_P_picks = pickle.load(fp)

        # creat extra columns
        df_P_picks[['network', 'others']] = df_P_picks['id'].str.split('.', 1, expand=True)
        df_P_picks[['station_code', 'date']] = df_P_picks['others'].str.split('.', 1, expand=True)
        df_P_picks = df_P_picks.drop(['date', 'others'], axis=1)

        # find common station_code in catalog and PhaseNet
        boolean_column = catalog_DF_P_picks['station_code'].isin(df_P_picks['station_code'])
        catalog_DF_P_picks = catalog_DF_P_picks[(boolean_column==True)]
        all_dists = np.array([])
        common_stations = catalog_DF_P_picks['station_code'].unique()

        # Creat an empty DataFrame file to store all UTC time of PhaseNet in common station
        all_p_picks_exist_in_catalogtory = pd.DataFrame(index =[])

        # loop over all common station
        for i in common_stations:
            bo = catalog_DF_P_picks['station_code']==i
            catalog_filter_station = catalog_DF_P_picks[(bo==True)]
            ao = df_P_picks['station_code']==i
            phasenet_filter_station = df_P_picks[(ao==True)]

            # Convert UTC time to datetime64[ms] (millisecond)
            a = catalog_filter_station.picks_time.to_numpy(dtype='datetime64[ms]')[:, np.newaxis].astype("float")
            b = phasenet_filter_station.timestamp.to_numpy(dtype='datetime64[ms]')[:, np.newaxis].astype("float")

            # Calculate P1 norme of all datetime64[ms]
            dist_mat = distance_matrix(a,b, p=1)
            dists = np.min(dist_mat, axis=1)
            all_dists = np.append(all_dists, dists)

            # append phasenet_filter_station
            min_index = np.argmin(dist_mat, axis=1)

            #phasenet_filter_station = phasenet_filter_station[min_index]
            phasenet_filter_station = phasenet_filter_station.iloc[min_index,:]

            all_p_picks_exist_in_catalogtory = pd.concat([all_p_picks_exist_in_catalogtory, phasenet_filter_station], axis=0)

        # Filter the time lag with the given threshold and capture the picks with more than 2 second time lag
        dists_filter_lag_time_m=all_dists[all_dists >= self.time_lag_threshold]

        # Perform P picks Quality control of PhaseNet by using existing P picks catalog with more than 2 second time lag
        fig_lag_m, ax_lag_m = plt.subplots(figsize=(20,10))
        n_lag_m, bins_lag_m, patches_lag_m = ax_lag_m.hist(dists_filter_lag_time_m, 20, density=False, facecolor='b', alpha=0.75)
        steps = (max(dists_filter_lag_time_m) - min(dists_filter_lag_time_m))/20
        plt.xticks(np.arange(min(dists_filter_lag_time_m), max(dists_filter_lag_time_m), step=steps))
        plt.xlabel('Time lag between catalog and PhaseNet (ms)', fontsize=18)
        plt.ylabel('Frequency', fontsize=18)
        plt.title('P picks Quality control of PhaseNet (2012-01-01 to 2012-01-31) with more 2s time lag', fontsize=21)
        plt.xlim(min(bins_lag_m), max(bins_lag_m))
        plt.grid(True)
        file_name = '{0}.{extention}'.format('P picks Quality control of PhaseNet (2012-01-01 to 2012-01-31) with more than 2s time lag', extention='png')
        fig_lag_m.savefig(os.path.join(self.export_DF_path, file_name), facecolor = 'w')
        
        # Filter the time lag with the given threshold and capture the picks with less than 2 second time lag
        dists_filter_lag_time=all_dists[all_dists < self.time_lag_threshold]

        # Perform P picks Quality control of PhaseNet by using existing P picks catalog with less than 2 second time lag
        fig_lag, ax_lag = plt.subplots(figsize=(20,10))
        n_lag, bins_lag, patches_lag = ax_lag.hist(dists_filter_lag_time, 20, density=False, facecolor='b', alpha=0.75)
        steps = (max(dists_filter_lag_time) - min(dists_filter_lag_time))/20
        plt.xticks(np.arange(min(dists_filter_lag_time), max(dists_filter_lag_time), step=steps))
        plt.xlabel('Time lag between catalog and PhaseNet (ms)', fontsize=18)
        plt.ylabel('Frequency', fontsize=18)
        plt.title('P picks Quality control of PhaseNet (2012-01-01 to 2012-01-31)', fontsize=21)
        plt.xlim(min(bins_lag), max(bins_lag))
        plt.grid(True)
        file_name = '{0}.{extention}'.format('P picks Quality control of PhaseNet (2012-01-01 to 2012-01-31)', extention='png')
        fig_lag.savefig(os.path.join(self.export_DF_path, file_name), facecolor = 'w')
        
        
        # Plot the histogram probability of all P picks PhaseNet in the common stations 
        
        all_p_picks_exist_in_catalogtory=all_p_picks_exist_in_catalogtory.iloc[all_dists < self.time_lag_threshold]
        
        fig0, ax0 = plt.subplots(figsize=(20,10))
        label_co = '{0}{1}{2}'.format('Common P picks in catalog with less than 2 seconds time-lag (',all_p_picks_exist_in_catalogtory.shape[0], ' P picks)')
        n_co, bins_co, patches_co = ax0.hist(all_p_picks_exist_in_catalogtory.prob, 21, density=False, alpha=0.75, label=label_co)
        label_all = '{0}{1}{2}'.format('All PhaseNet P picks (',df_P_picks.shape[0], ' P picks)')
        ax0.hist(df_P_picks.prob, 21, density=False, color = "skyblue", ec="skyblue", alpha=0.75, label= label_all)
        steps = (max(all_p_picks_exist_in_catalogtory.prob) - min(all_p_picks_exist_in_catalogtory.prob))/21
        plt.xticks(np.arange(min(all_p_picks_exist_in_catalogtory.prob), max(all_p_picks_exist_in_catalogtory.prob), step=steps))
        plt.xlabel('PhaseNet P picks Probability', fontsize=18)
        plt.ylabel('Frequency', fontsize=18)
        plt.title('PhaseNet output P picks(2012-01-01 to 2012-01-31)', fontsize=21)
        plt.xlim(min(bins_co), max(bins_co))
        plt.grid(True)
        plt.legend(loc='upper right')
        file_name = '{0}.{extention}'.format('PhaseNet output P picks(2012-01-01 to 2012-01-31)', extention='png')
        fig0.savefig(os.path.join(self.export_DF_path, file_name), facecolor = 'w')
        
        # Perform P picks Quality control of PhaseNet by using existing P picks catalog with defined time lag 
        lag_time = all_dists[all_dists < self.time_lag_threshold]
        for j in range (1, bins_lag.shape[0]):
            select_p_picks=all_p_picks_exist_in_catalogtory.iloc[(lag_time < bins_lag[j]) & (lag_time >= bins_lag[j-1])]
            fig, ax = plt.subplots(figsize=(20,10))
            ax.hist(select_p_picks.prob, 21, density=False, color = "b", ec="b", alpha=0.75)
            plt.xlabel('PhaseNet P picks Probability', fontsize=18)
            plt.ylabel('Frequency', fontsize=18)
            title_name = '{0}{1}{2}{3}{4}'.format('Common P picks in catalog with ',round (bins_lag[j-1]),' - ', round (bins_lag[j]), ' time lag (ms)')
            plt.title(title_name, fontsize=21)
            file_name = '{0}{1}.{extention}'.format('PhaseNet_result_P_bins: ',round (bins_lag[j]), extention='png')
            fig.savefig(os.path.join(self.export_DF_path, file_name), facecolor = 'w')
        

    def compare_PhaseNet_catalog_S_picks (self):

        '''
        This function compares the result of PhaseNet and existing catalog.
        Parameters:
                    - catalog_DF_S_picks   (DataFrame): catalog S picks
                    - df_S_picks           (DataFrame): PhaseNet S picks
        '''

        # catalog_DF_P_picks, df_P_picks
        with open(os.path.join(self.export_DF_path, "PhaseNet_result_s_picks.pkl"),'rb') as fp:
            df_S_picks = pickle.load(fp)

        with open(os.path.join(self.export_DF_path, "catalog_s_picks.pkl"),'rb') as fp:
            catalog_DF_S_picks = pickle.load(fp)

        # creat extra columns
        df_S_picks[['network', 'others']] = df_S_picks['id'].str.split('.', 1, expand=True)
        df_S_picks[['station_code', 'date']] = df_S_picks['others'].str.split('.', 1, expand=True)
        df_S_picks = df_S_picks.drop(['date', 'others'], axis=1)

        # find common station_code in catalog_DF_P_picks
        boolean_column = catalog_DF_S_picks['station_code'].isin(df_S_picks['station_code'])
        catalog_DF_S_picks = catalog_DF_S_picks[(boolean_column==True)]
        all_dists = np.array([])
        common_stations = catalog_DF_S_picks['station_code'].unique()

        # Creat an empty DataFrame file to store all UTC time of PhaseNet in common station
        all_s_picks_exist_in_catalogtory = pd.DataFrame(index =[])
        
        # loop over all common statio
        for i in common_stations:
            bo = catalog_DF_S_picks['station_code']==i
            catalog_filter_station = catalog_DF_S_picks[(bo==True)]
            ao = df_S_picks['station_code']==i
            phasenet_filter_station = df_S_picks[(ao==True)]

            # Convert UTC time to datetime64[ms] (millisecond)
            a = catalog_filter_station.picks_time.to_numpy(dtype='datetime64[ms]')[:, np.newaxis].astype("float")
            b = phasenet_filter_station.timestamp.to_numpy(dtype='datetime64[ms]')[:, np.newaxis].astype("float")

            # Calculate P1 norme of all datetime64[m
            dist_mat = distance_matrix(a,b, p=1)
            dists = np.min(dist_mat, axis=1)
            all_dists = np.append(all_dists, dists)

            # append phasenet_filter_station
            min_index = np.argmin(dist_mat, axis=1)

            #phasenet_filter_station = phasenet_filter_station[min_index]
            phasenet_filter_station = phasenet_filter_station.iloc[min_index,:]

            all_s_picks_exist_in_catalogtory = pd.concat([all_s_picks_exist_in_catalogtory, phasenet_filter_station], axis=0)
    
        # Filter the time lag with the given threshold and capture the picks with more than 2 second time lag
        dists_filter_lag_time_m=all_dists[all_dists >= self.time_lag_threshold]

        # Perform S picks Quality control of PhaseNet by using existing S picks catalog with more than 2 second time lag
        fig_lag_m, ax_lag_m = plt.subplots(figsize=(20,10))
        n_lag_m, bins_lag_m, patches_lag_m = ax_lag_m.hist(dists_filter_lag_time_m, 20, density=False, facecolor='r', alpha=0.75)
        steps = (max(dists_filter_lag_time_m) - min(dists_filter_lag_time_m))/20
        plt.xticks(np.arange(min(dists_filter_lag_time_m), max(dists_filter_lag_time_m), step=steps))
        plt.xlabel('Time lag between catalog and PhaseNet (ms)', fontsize=18)
        plt.ylabel('Frequency', fontsize=18)
        plt.title('S picks Quality control of PhaseNet (2012-01-01 to 2012-01-31) with more 2s time lag', fontsize=21)
        plt.xlim(min(bins_lag_m), max(bins_lag_m))
        plt.grid(True)
        file_name = '{0}.{extention}'.format('S picks Quality control of PhaseNet (2012-01-01 to 2012-01-31) with more 2s time lag', extention='png')
        fig_lag_m.savefig(os.path.join(self.export_DF_path, file_name), facecolor = 'w')


        # Filter the time lag with the given threshold and capture the picks with less than 2 second time lag
        dists_filter_lag_time=all_dists[all_dists < self.time_lag_threshold]

        # Perform S picks Quality control of PhaseNet by using existing S picks catalog with less than 2 second time lag
        fig_lag, ax_lag = plt.subplots(figsize=(20,10))
        n_lag, bins_lag, patches_lag = ax_lag.hist(dists_filter_lag_time, 20, density=False, facecolor='r', alpha=0.75)
        steps = (max(dists_filter_lag_time) - min(dists_filter_lag_time))/20
        plt.xticks(np.arange(min(dists_filter_lag_time), max(dists_filter_lag_time), step=steps))
        plt.xlabel('Time lag between catalog and PhaseNet (ms)', fontsize=18)
        plt.ylabel('Frequency', fontsize=18)
        plt.title('S picks Quality control of PhaseNet (2012-01-01 to 2012-01-31)', fontsize=21)
        plt.xlim(min(bins_lag), max(bins_lag))
        plt.grid(True)
        file_name = '{0}.{extention}'.format('S picks Quality control of PhaseNet (2012-01-01 to 2012-01-31)', extention='png')
        fig_lag.savefig(os.path.join(self.export_DF_path, file_name), facecolor = 'w')
        
        
        # Plot the histogram probability of all S picks PhaseNet in the common stations 
        all_s_picks_exist_in_catalogtory=all_s_picks_exist_in_catalogtory.iloc[all_dists < self.time_lag_threshold]
        
        fig0, ax0 = plt.subplots(figsize=(20,10))
        label_co = '{0}{1}{2}'.format('Common S picks in catalog with less than 2 seconds time-lag (',all_s_picks_exist_in_catalogtory.shape[0], ' S picks)')
        n_co, bins_co, patches_co = ax0.hist(all_s_picks_exist_in_catalogtory.prob, 21, density=False, alpha=0.75, label=label_co)
        label_all = '{0}{1}{2}'.format('All PhaseNet S picks (',df_S_picks.shape[0], ' S picks)')
        ax0.hist(df_S_picks.prob, 21, density=False, color = "skyblue", ec="skyblue", alpha=0.75, label= label_all)
        steps = (max(all_s_picks_exist_in_catalogtory.prob) - min(all_s_picks_exist_in_catalogtory.prob))/21
        plt.xticks(np.arange(min(all_s_picks_exist_in_catalogtory.prob), max(all_s_picks_exist_in_catalogtory.prob), step=steps))
        plt.xlabel('PhaseNet S picks Probability', fontsize=18)
        plt.ylabel('Frequency', fontsize=18)
        plt.title('PhaseNet output S picks(2012-01-01 to 2012-01-31)', fontsize=21)
        plt.xlim(min(bins_co), max(bins_co))
        plt.grid(True)
        plt.legend(loc='upper right')
        file_name = '{0}.{extention}'.format('PhaseNet output S picks(2012-01-01 to 2012-01-31)', extention='png')
        fig0.savefig(os.path.join(self.export_DF_path, file_name), facecolor = 'w')
        
        # Perform S picks Quality control of PhaseNet by using existing S picks catalog with defined time lag 
        lag_time = all_dists[all_dists < self.time_lag_threshold]
        for j in range (1, bins_lag.shape[0]):
            select_s_picks=all_s_picks_exist_in_catalogtory.iloc[(lag_time < bins_lag[j]) & (lag_time >= bins_lag[j-1])]
            fig, ax = plt.subplots(figsize=(20,10))
            ax.hist(select_s_picks.prob, 21, density=False, color = "r", ec="r", alpha=0.75)
            plt.xlabel('PhaseNet S picks Probability', fontsize=18)
            plt.ylabel('Frequency', fontsize=18)
            title_name = '{0}{1}{2}{3}{4}'.format('Common S picks in catalog with ',round (bins_lag[j-1]),' - ', round (bins_lag[j]), ' time lag (ms)')
            plt.title(title_name, fontsize=21)
            file_name = '{0}{1}.{extention}'.format('PhaseNet_result_S_bins: ',round (bins_lag[j]), extention='png')
            fig.savefig(os.path.join(self.export_DF_path, file_name), facecolor = 'w')

if __name__ == "__main__":

    phasenet_direc = '/home/javak/phasenet_chile-subduction-zone'
    chile_GFZ_online_direc = '/data2/chile/CHILE_GFZ_ONLINE'
    export_DF_path = '/home/javak/Sample_data_chile/Comparing PhaseNet and Catalog'
    export_mseed_path = '/home/javak/Sample_data_chile/mseed'
    working_direc = '/home/javak/Sample_data_chile'
    picks_name = '2012_events.pkl'

    start_year_analysis = 2012
    start_day_analysis = 1
    end_year_analysis = 2012
    end_day_analysis = 31
    analysis = False
    time_lag_threshold = 2000

    obj = PhaseNet_Analysis (phasenet_direc,chile_GFZ_online_direc,export_DF_path, 
                            export_mseed_path, working_direc, picks_name, 
                            start_year_analysis, start_day_analysis,
                            end_year_analysis, end_day_analysis, analysis, time_lag_threshold)
    
    #result = obj.compare_PhaseNet_catalog_P_picks()
    result = obj()