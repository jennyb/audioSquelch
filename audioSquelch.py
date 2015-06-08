#!/usr/bin/python
from sys import byteorder
from array import array
from struct import pack

import pyaudio
import wave
import Hamlib
import sys 
import time
import os.path
import ConfigParser
from recorder import Recorder
from datetime import datetime
import csv

DATE_FORMAT = '%Y%m%d%H%M%S'
CONFIG = '/media/USB1/asq.txt'
FILENAME = 'audio.wav'
FILEPATH = '/media/USB1/'
RESULTS_FILE = '/media/USB1/results.csv'

THRESHOLD = 500
CHUNK_SIZE = 2048
FORMAT = pyaudio.paInt16
RATE = 44100
CHANNELS = 1 #audio channels
START_TIME = 2
STOP_TIME = 5
MIN_QSO_TIMER = 30
MAX_SAMPLE_TIMER = 60
HOLDOFF_TIME = 600
RSSI_COUNT = 60 	#read a value every second and write the average every minute
RSSI_OFFSET = 52	# on the IC-R20 the minimum RSSI value is -52. This makes all the values positive
RSSI_THRESHOLD = 40	

def callback(snd_data, frame_count, time_info, status):	
	return (snd_data, pyaudio.paContinue)
	
def writeResults(level):
	try:
		results_file = open( RESULTS_FILE, 'a')
		csv_writer=csv.writer(results_file, delimiter=',', quotechar='|',quoting=csv.QUOTE_MINIMAL)
		csv_writer.writerow ([str(datetime.now()),level]) 
		results_file.close()
	except:
		print "Failed to open %s" % RESULTS_FILE


if __name__ == '__main__':
	print "Python",sys.version[:5],"test,", Hamlib.cvar.hamlib_version
	
	rec = Recorder(channels=1)
	rssiCounter=0
	cumulativeRssi=0
	
	
	config=ConfigParser.ConfigParser()
	dataSet = config.read(CONFIG)
	if len( dataSet ) != 1:
		print "Failed to open config file: %s" % CONFIG
		exit(-1)
				 
	radioType = config.getint("main","radio")
	radioFrequency = config.getint("main","frequency")
	radioMode = config.get("main","mode")

	print radioMode
	print radioFrequency
	print radioType
	
	#Hamlib.rig_set_debug (Hamlib.RIG_DEBUG_TRACE)
	Hamlib.rig_set_debug (Hamlib.RIG_DEBUG_NONE)

	# Init Set up for AR8200
	# my_rig = Hamlib.Rig (Hamlib.RIG_MODEL_AR8200)
	# my_rig.set_conf ("rig_pathname","/dev/ttyUSB0")hamlib icom r20
		
	# Init setup for IC-R20
	#my_rig = Hamlib.Rig (Hamlib.RIG_MODEL_ICR20)
	my_rig = Hamlib.Rig (radioType)
	my_rig.set_conf ("rig_pathname","/dev/icomCiv") #this is called icomCiv for historical reasons
	my_rig.set_conf ("retry","5")

	my_rig.open ()

	my_rig.set_vfo (Hamlib.RIG_VFO_A)
	my_rig.set_freq (radioFrequency)

	print "freq:",my_rig.get_freq()

	my_rig.set_mode(Hamlib.RIG_MODE_WFM)
	(mode, width) = my_rig.get_mode()
	print "mode:",Hamlib.rig_strrmode(mode),", bandwidth:",width
		
		
	state = 'IDLE'
	startTimer = START_TIME
	stopTimer = STOP_TIME
	timeCounter = 0 # This counter the number of seconds of transmission. Cull files > 30 seconds 

	while True :
		rssi = my_rig.get_level_i(Hamlib.RIG_LEVEL_STRENGTH) + RSSI_OFFSET
		if state == 'IDLE' :
			print 'IDLE=> RSSI: {}'.format(rssi)
			if rssi > RSSI_THRESHOLD : # Squelch open
				state = 'START_TIMER'
				startTimer = START_TIME

		elif state == 'START_TIMER' :
			print 'START_TIMER=> Start Timer: {} RSSI: {}'.format(startTimer, rssi)
			if rssi <= RSSI_THRESHOLD : # Squelch closed
				state = 'IDLE'
			else :
				if startTimer < 1 :
					#Start recording
					state = 'RECORDING'
					#record_to_file('%s%s_%s' % (FILEPATH,datetime.now().strftime(DATE_FORMAT),FILENAME))
					recFileName =  '%s%s_%s' % (FILEPATH,datetime.now().strftime(DATE_FORMAT),FILENAME)
					recFile = rec.open(recFileName, 'wb') 
					recFile.start_recording()
					recordingFlag = 1
					timeCounter = 0
				else :
					startTimer -= 1

		elif state == 'RECORDING' :
			print 'RECORDING=> TimeCounter: {} RSSI: {}'.format(timeCounter,rssi)
			timeCounter += 1
			if rssi <= RSSI_THRESHOLD: # Squelch closed
				stopTimer = STOP_TIME
				state = 'STOP_TIMER'
			if timeCounter > MAX_SAMPLE_TIMER: # we only want a sample 
				recFile.stop_recording()
				recordingFlag = 0
				holdOffTimer=0
				state = 'TIMEOUT'

		elif state == 'TIMEOUT' :
			print 'TIMEOUT=> Squelch open - holdOffTimer: {} RSSI: {}'.format(holdOffTimer,rssi)
			holdOffTimer += 1
			if holdOffTimer > HOLDOFF_TIME: #Time to get the next sample
				state = 'IDLE'
			if rssi <= RSSI_THRESHOLD: # Squelch closed
				state = 'IDLE'
		
				
		elif state == 'STOP_TIMER':
			print 'STOP_TIMER=> Stop Timer: {}  rssi: {}'.format(stopTimer,rssi) 
			timeCounter += 1
			if rssi <= RSSI_THRESHOLD: # Squelch closed
				if stopTimer < 1 :
					#stop recording
					recFile.stop_recording()
					state = 'IDLE'
					recordingFlag = 0
					if timeCounter < MIN_QSO_TIMER:
						os.remove(recFileName)
				else :
					stopTimer -= 1
					
		if rssiCounter > RSSI_COUNT:
			aveRssi = cumulativeRssi/RSSI_COUNT
			writeResults(aveRssi)
			cumulativeRssi = 0
			rssiCounter = 0
		else : 
			cumulativeRssi += rssi 	
			rssiCounter += 1			
		
		time.sleep(1)



