#----------------------------------------------------------------------
#     QuantumBowtiePing.qiskit
#       by KPRoche (Kevin P. Roche) (c) 2017,2018,2019
#
#     Connect to the IBM Quantum Experience site via the QISKIT IBMQ functions
#             run OPENQASM code on the simulator there
#     Display the results using the 8x8 LED array on a SenseHat
#     Spin off the display functions in a separate thread so they can exhibit
#             smooth color changes while "thinking"
#     Use a ping function to try to make sure the website is available before
#             sending requests and thus avoid more hangs that way
#     Move the QASM code into an outside file
#     March 2018 -- Detect a held center switch on the SenseHat joystick to trigger shutdown
#     July 2019 -- convert to using QISKIT full library authentication and quantum circuit
#                    techniques
#----------------------------------------------------------------------


# import the necessary modules
print("importing libraries...")
print("       ....sys")
import sys                             # used to check for passed filename
print("       ....os")
import os                              # used to find script directory
print("       ....requests")
import requests                        # used for ping
print("       ....threading")
from threading import Thread           # used to spin off the display functions
print("       ....colorsys")
from colorsys import hsv_to_rgb        # used to build the color array
print("       ....time")
from time import process_time          # used for loop timer
print("       ....sleep")
from time import sleep                 # used for delays
print("       ....SenseHat")
from sense_hat import SenseHat         # class for controlling the SenseHat
print("       ....qiskit")
from qiskit import IBMQ, QuantumCircuit, execute, transpile               # classes for accessing the Quantum Experience IBMQ
print("       ....qiskit.providers JobStatus")
from qiskit.providers import JobStatus
# This is temporary because the libraries are changing again
import warnings
print("       ....warnings")
warnings.filterwarnings("ignore", category=DeprecationWarning) 

# some variables we are going to need as we start up

print("Setting up...")

result = None
runcounter=0
maxpattern='00000'
interval=5
hat = SenseHat() # instantiating hat right away so we can use it in functions
thinking=False    # used to tell the display thread when to show the result
shutdown=False    # used to tell the display thread to trigger a shutdown
qdone=False
showlogo=False

###########################################################################################
#-------------------------------------------------------------------------------    
#   These variables and functions are for lighting up the qubit display on the SenseHat
#                 ibm_qx5 builds a "bowtie" 
#           They were moved up here so we can flash a "Q" as soon as the libraries load
#              
#   the color shift effect is based on the rainbow example included with the SenseHat library
#-------------------------------------------------------------------------------

# pixel coordinates to draw the bowtie qubits or the 16 qubit array
ibm_qx5 = [[40,41,48,49],[8,9,16,17],[28,29,36,37],[6,7,14,15],[54,55,62,63]]
ibm_qx16 = [[63],[54],[61],[52],[59],[50],[57],[48],
            [7],[14],[5],[12],[3],[10],[1],[8]]
            #[[0],[9],[2],[11],[4],[13],[6],[15],
            #[56],[49],[58],[51],[60],[53],[62],[55]]

# global to spell OFF in a single operation
X = [255, 255, 255]  # white
O = [  0,   0,   0]  # black

off = [
   O, O, O, O, O, O, O, O,
   O, X, O, X, X, O, X, X,
   X, O, X, X, O, O, X, O,
   X, O, X, X, X, O, X, X,
   X, O, X, X, O, O, X, O,
   O, X, O, X, O, O, X, O,
   O, O, O, O, O, O, O, O,
   O, O, O, O, O, O, O, O,
   ]

Qlogo = [
   O, O, O, X, X, O, O, O,
   O, O, X, O, O, X, O, O,
   O, O, X, O, O, X, O, O,
   O, O, X, O, O, X, O, O,
   O, O, X, O, O, X, O, O,
   O, O, O, X, X, O, O, O,
   O, O, O, O, X, O, O, O,
   O, O, O, X, X, O, O, O,
   ]

# setting up the 8x8=64 pixel variables for color shifts

hues = [
    0.00, 0.00, 0.06, 0.13, 0.20, 0.27, 0.34, 0.41,
    0.00, 0.06, 0.13, 0.21, 0.28, 0.35, 0.42, 0.49,
    0.07, 0.14, 0.21, 0.28, 0.35, 0.42, 0.50, 0.57,
    0.15, 0.22, 0.29, 0.36, 0.43, 0.50, 0.57, 0.64,
    0.22, 0.29, 0.36, 0.44, 0.51, 0.58, 0.65, 0.72,
    0.30, 0.37, 0.44, 0.51, 0.58, 0.66, 0.73, 0.80,
    0.38, 0.45, 0.52, 0.59, 0.66, 0.73, 0.80, 0.87,
    0.45, 0.52, 0.60, 0.67, 0.74, 0.81, 0.88, 0.95,
    ]

pixels = [hsv_to_rgb(h, 1.0, 1.0) for h in hues]

# scale lets us do a simple color rotation of hues and convert it to RGB in pixels

def scale(v):
    return int(v * 255)

def resetrainbow(show=False):
   global pixels,hues
   pixels = [hsv_to_rgb(h, 1.0, 1.0) for h in hues]
   pixels = [(scale(r), scale(g), scale(b)) for r, g, b in pixels]
   if (show): hat.set_pixels(pixels)

def showqubits(pattern='0000000000000000'):
   global hat
   for p in range(64):          #first set all pixels off
           pixels[p]=[0,0,0]
   for q in range(len(display)):
      if pattern[q]=='1':         # if the digit is "1" assign blue
         for p in display[q]:
            pixels[p]=[0,0,255]
      else:                       # otherwise assign it red
         for p in display[q]:
            pixels[p]=[255,0,0]

   hat.set_pixels(pixels)         # turn them all on


#--------------------------------------------------
#    blinky lets us use the rainbow rotation code to fill the bowtie pattern
#       it can be interrupted by tapping the joystick or if
#       an experiment ID is provided and the 
#       status returns "DONE"
#
#------------------------------------------------------

def blinky(time=20,experimentID=''):
   global pixels,hues,experiment, Qlogo, showlogo
   #resetrainbow()
   count=0
   GoNow=False
   while ((count*.02<time) and (not GoNow)):
      # Rotate the hues
      hues = [(h + 0.01) % 1.0 for h in hues]
      # Convert the hues to RGB values
      pixels = [hsv_to_rgb(h, 1.0, 1.0) for h in hues]
      # hsv_to_rgb returns 0..1 floats; convert to ints in the range 0..255
      pixels = [(scale(r), scale(g), scale(b)) for r, g, b in pixels]
      for p in range(64):
         if p in sum(display,[]):
            pass
         else:
            pixels[p]=[0,0,0]
      if (result is not None):
         if (result.status=='COMPLETED'):
            GoNow=True
    # Update the display
      if not showlogo:
          hat.set_pixels(pixels)
      else:
          hat.set_pixels(Qlogo)
      sleep(0.002)
      count+=1
      for event in hat.stick.get_events():
         if event.action == 'pressed':
            goNow=True
         if event.action == 'held' and event.direction =='middle':
            shutdown=True 


#------------------------------------------------
#  now that the light pattern functions are defined,
#    build a class glow so we can launch display control as a thread
#------------------------------------------------
class glow():
   global thinking,hat, maxpattern, shutdown,off,Qlogo

   def __init__(self):
      self._running = True
      
   def stop(self):
      self._running = False
      self._stop = True

   def run(self):
      #thinking=False
      while self._running:
         if shutdown:
            hat.set_rotation(180)
            hat.set_pixels(off)
            sleep(1)
            hat.clear()
            path = 'sudo shutdown -P now '
            os.system (path)
         else:
           if thinking:
              blinky(.1)
           else:
              showqubits(maxpattern)


#----------------------------------------------------------------
# Set the display size and Turn on the display with an IBM "Q" logo
#----------------------------------------------------------------
display=ibm_qx16
hat.set_rotation(180)
hat.set_pixels(Qlogo)


##################################################################
#   Input file functions
##################################################################

#----------------------------------------------------------
# find our experiment file... alternate can be specified on command line
#       use a couple tricks to make sure it is there
#       if not fall back on our default file
#def loadQASMfile():

scriptfolder = os.path.dirname(os.path.realpath("__file__"))
print(sys.argv)
print ("Number of arguments: ",len(sys.argv))
# look for a filename option
if (len(sys.argv) > 1) and type(sys.argv[1]) is str:
  #print (type(sys.argv[1]))
  qasmfilename=sys.argv[1]
  print ("input arg:",qasmfilename)
  if (qasmfilename == '16'):    qasmfilename='expt16.qasm' 
else:
  qasmfilename='expt.qasm'

#complete the path if necessary
if ('/' not in qasmfilename):
  qasmfilename=scriptfolder+"/"+qasmfilename
if (not os.path.isfile(qasmfilename)):
    qasmfilename=scriptfolder+"/"+'expt.qasm'
    
print("OPENQASM file: ",qasmfilename)
if (not os.path.isfile(qasmfilename)):
    print("QASM file not found... exiting.")
    exit()
# end DEF ----------------------

###############################################################
#   Connection functions
#       ping and authentication
###############################################################

#----------------------------------------------------------------------------
# set up a ping function so we can confirm the IBMQ can connect before we attempt it
#           ping uses the requests library
#           based on pi-ping by Wesley Archer (raspberrycoulis) (c) 2017
#           https://github.com/raspberrycoulis/Pi-Ping
#----------------------------------------------------------------------------
def ping(website='https://quantumexperience.ng.bluemix.net',repeats=1,wait=0.5,verbose=False):
  msg = 'ping response'
  for n in range(repeats):
    response = requests.get(website)
    if int(response.status_code) == 200: # OK
        pass
    elif int(response.status_code) == 500: # Internal server error
        msg ='Internal server error'
    elif int(response.status_code) == 503: # Service unavailable
        msg = 'Service unavailable'
    elif int(response.status_code) == 502: # Bad gateway
        msg = 'Bad gateway'
    elif int(response.status_code) == 520: # Cloudflare: Unknown error
        msg = 'Cloudflare: Unknown error'
    elif int(response.status_code) == 522: # Cloudflare: Connection timed out
        msg = 'Cloudflare: Connection timed out'
    elif int(response.status_code) == 523: # Cloudflare: Origin is unreachable
        msg = 'Cloudflare: Origin is unreachable'
    elif int(response.status_code) == 524: # Cloudflare: A Timeout occurred
        msg = 'Cloudflare: A Timeout occurred'
    if verbose: print(response.status_code,msg)
    if repeats>1: time.sleep(wait)
    
  return int(response.status_code)
# end DEF ----------------------------------------------------------------




# ------------------------------------------------------------------------
#  try to start our IBMQ connection to IBM QE
#       Here we attempt to ping the IBM Quantum Experience website. If no response, we exit
#       If we get a 200 response, the site is live and we initialize our connection to it
#-------------------------------------------------------------------------------
def startIBMQ():
    #global IBMQ
    print ('Pinging IBM Quantum Experience before start')
    p=ping('https://api.quantum-computing.ibm.com',1,0.5,True)

    if p==200:
        IBMQ.load_accounts()
    else:
        exit()
#-------------------------------------------------------------------------------


#################################################################################
#
#   Main program loop  (note: we turned on a "Q" earlier at line 202)
#
#################################################################################



# Instantiate an instance of our glow class
print("Instantiating glow...")
glowing = glow()

#-------------------------------------------------
#  OK, let's get this shindig started
#-------------------------------------------------
            
rainbowTie = Thread(target=glowing.run)     # create the display thread
startIBMQ()                                  # try to connect and instantiate the IBMQ 

exptfile = open(qasmfilename,'r') # open the file with the OPENQASM code in it
qasm= exptfile.read()            # read the contents into our experiment string

if (len(qasm)<5):                # if that is too short to be real, exit
    exit
else:                            # otherwise print it to the console for reference
    print("OPENQASM code to send:\n",qasm)
    
qcirc=QuantumCircuit.from_qasm_str(qasm)   
print (qcirc)
if (qcirc.width()/2 > 5):
    display=ibm_qx16
    maxpattern='0000000000000000'
    print ("circuit width: ",qcirc.width()/2," using 16 qubit display")
else:
    display=ibm_qx5
    maxpattern='00000'
    print ("circuit width: ",qcirc.width()/2," using 5 qubit display")
backend='ibmq_qasm_simulator'             # specify the simulator as the backend
#backend='simulator' 
rainbowTie.start()                          # start the display thread
Q=IBMQ.get_backend(backend)

while True:
   runcounter += 1
   
   try:
       p=ping()
   except:
       print("connection problem with IBMQ")
   else:
       if p==200:
           showlogo = True
           thinking = True
           backend_status = Q.status()  # check the availability
           print('Backend Status: ',backend_status.status_msg)
           if Q.status().status_msg == 'active':
               
               print('     executing quantum circuit...')
               print(qcirc)
               qjob=execute(qcirc, Q, shots=500, memory=False)
               showlogo =  False
               qdone = False
               while not qdone:
                   #result=qjob.result()     # get the result
                   try:
                       qstatus = qjob.status()
                   except:
                       print("Problem getting status, trying again...")
                   else: 
                       print(runcounter,": ",qstatus)
                       if qstatus == JobStatus.DONE :
                            qdone = True
               # only get here once we get DONE status
               result=qjob.result()     # get the result
               counts=result.get_counts(qcirc)   
               maxpattern=max(counts,key=counts.get)
               maxvalue=counts[maxpattern]
               print("Maximum value:",maxvalue, "Maximum pattern:",maxpattern)
               thinking = False  # this cues the display thread to show the qubits in maxpattern
               
           else:
                print(backend,'busy; waiting to try again')
       else:
            print(p,'response to ping; waiting to try again')

   goAgain=False                    # wait to do it again
   print('Waiting ',interval,'s before next run...')
   
   myTimer=process_time()
   while not goAgain:
      for event in hat.stick.get_events():   
         if event.action == 'pressed':      #somebody tapped the joystick -- go now
            goAgain=True
            blinky(.001)
            hat.set_pixels(pixels)
         if event.action == 'held' and event.direction =='middle':
            shutdown=True 
         
      if (process_time()-myTimer>interval):       # 10 seconds elapsed -- go now
            goAgain=True
