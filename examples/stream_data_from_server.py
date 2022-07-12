
from biosiglive.streaming.client import Client, Message
import numpy as np
import pandas as pd
from biosiglive.processing.mappEMG import Mapper
from biosiglive.processing.mappEMG import EMGprocess
from biosiglive.processing.mappEMG import Emitter
from time import sleep

if __name__ == '__main__':

    print("Client starting...")

    type_of_data = ["emg"]

    # Server's host and port
    input_host_ip = input("\nConnect to host address (leave empty for \"localhost\"): ")
    host_ip = 'localhost' if input_host_ip == '' else input_host_ip
    input_host_port = input("\nConnect to host address (leave empty for \"5005\"): ")
    host_port = 5005 if input_host_port == '' else int(input_host_port)

    
    dummy_message = Message(command=["emg"],
                      read_frequency=100,
                      nb_frame_to_get=1,
                      get_raw_data=False,
                      mvc_list=None)
    client = Client(server_ip=host_ip, port=host_port, type="TCP")

    # Get data streamed from server
    data = client.get_data(dummy_message)
    sleep(1)
    system_rate = data['system_rate'][0]
    read_freq = data['sampling_rate'][0]
    n_electrode = data['n_electrode'][0]

    # Load MVC data from previous trials or random
    load_mvc = None
    while load_mvc not in ['y', 'n']:
        load_mvc = input("\nDo you want to load real MVC values? ('y' or 'n' for random): ")

    if load_mvc == 'n':
        list_mvc = np.random.rand(n_electrode, 1).tolist()
    else:
        mvc_file = input("\nInput name of the MVC .csv file (for example \"MVC_20220707-1915.csv\"): ")
        list_mvc = pd.read_csv(mvc_file)           # Open .csv file
        list_mvc = list_mvc.to_numpy().T.tolist()  # Get MVC in the proper shape

    # Prepare Message that will be used to get data from server
    # Number of frames to get comes from the server
    # depending on the device frequency
    message = Message(command=type_of_data,
                      read_frequency=read_freq,
                      nb_frame_to_get=system_rate,
                      get_raw_data=False,
                      mvc_list=list_mvc)


    ############## setup for post processing ##############

    ### initializing weights ###
    weights_raw = input("\nAttribute weights between 0 and 1 to each sensor (e.g for A1 A2 A3, write 0.45 1 0): ").split(" ")
    while len(weights_raw) != n_electrode or not (all(float(w) <= 1 for w in weights_raw)):
        print("\nNumber of weights does not correspond to number of channels or values are not between 0 and 1...")
        weights_raw = input("\nAttribute weights between 0 and 1 to each sensor (e.g for A1 A2 A3, write 0.45 1 0): ").split(" ")
    
    weights = np.empty((1,n_electrode))
    for i, w in enumerate(weights_raw):
        weights[0][i] = float(w)
    
    ### initializing post processor ###
    post_processor = EMGprocess()
   
    ### initializing mapper ###
    mapper = Mapper(n_electrode, system_rate) 

    ### initializing phones to which we send the haptics ###
    emitter = Emitter()
    emit = True
    n_devices = input('\nHow many devices with the haptics app would you like to connect? ')
    if int(n_devices) == 0:
        emit = False
    n = 1
    if emit == True:
        while n != int(n_devices)+ 1:
            ip = input(f'\nIP of device number {n} (e.g: XXX.XXX.X.X): ')
            port = input(f'\nPORT of device number {n} (e.g: 2222): ')
            ip = str(ip)
            port = int(port)
            try:
                emitter.add_device_client(ip,port)
                n = n + 1
            except:
                print("Invalid IP or PORT, try again...")

    ########################################################

    print("\nStart receiving from server...\n")

    while True:

        # Gets the data from the server.
        # Create a client to get data from server
        client = Client(server_ip=host_ip, port=host_port, type="TCP")
        # Get all the data streamed from server
        data = client.get_data(message)

        # Get only the emg data as a numpy array.
        emg = np.array(data['emg_server']) # you can also get sampling_rate and system_rate

        ##### PROCESSING #####
        perc_mvc = (emg/list_mvc)
        post_processor.input(perc_mvc) # inputting data to be processed
        post_processor.clip() # clipping data in case it is not between 0 and 1
        post_processor.slide() # smoothing the data
        data_tmp = post_processor.scale(1) # for now scaling to 1 as it's random data 

        ##### MAPPING & EMITTING #####
        mapper.input(data_tmp)
        weighted_avr = mapper.weighted_average(weights)
        if emit:
            for w in weighted_avr[0]:
                emitter.sendMessage(mapper.toFreqAmpl(w))
                sleep(0.5)

       
