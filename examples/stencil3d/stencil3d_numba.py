# Port of examples/charm++/load_balancing/stencil3d from Charm++ codebase
# This version uses NumPy and Numba
# NOTE: set LBPeriod very small so that AtSync doesn't wait

from charmpy import charm, Chare, Mainchare, Array, CkNumPes, when
from charmpy import readonlies as ro
import time
import math
import numpy as np
import numba

ro.initTime = time.time()

MAX_ITER = 100
LBPERIOD_ITER = 200     # LB is called every LBPERIOD_ITER number of program iterations
CHANGELOAD = 30
LEFT,RIGHT,TOP,BOTTOM,FRONT,BACK = range(6)
DIVIDEBY7 = 0.14285714285714285714

class Main(Mainchare):
  def __init__(self, args):

    if (len(args) != 3) and (len(args) != 7):
      print(args[0] + " [array_size] [block_size]")
      print("OR " + args[0] + " [array_size_X] [array_size_Y] [array_size_Z] [block_size_X] [block_size_Y] [block_size_Z]")
      charm.abort("Incorrect program arguments")

    if len(args) == 3:
      ro.arrayDimX = ro.arrayDimY = ro.arrayDimZ = int(args[1])
      ro.blockDimX = ro.blockDimY = ro.blockDimZ = int(args[2])
    elif len(args) == 7:
      ro.arrayDimX, ro.arrayDimY, ro.arrayDimZ = [int(arg) for arg in args[1:4]]
      ro.blockDimX, ro.blockDimY, ro.blockDimZ = [int(arg) for arg in args[4:7]]

    if (ro.arrayDimX < ro.blockDimX) or (ro.arrayDimX % ro.blockDimX != 0): charm.abort("array_size_X % block_size_X != 0!")
    if (ro.arrayDimY < ro.blockDimY) or (ro.arrayDimY % ro.blockDimY != 0): charm.abort("array_size_Y % block_size_Y != 0!")
    if (ro.arrayDimZ < ro.blockDimZ) or (ro.arrayDimZ % ro.blockDimZ != 0): charm.abort("array_size_Z % block_size_Z != 0!")

    ro.num_chare_x = ro.arrayDimX // ro.blockDimX
    ro.num_chare_y = ro.arrayDimY // ro.blockDimY
    ro.num_chare_z = ro.arrayDimZ // ro.blockDimZ

    print("\nSTENCIL COMPUTATION WITH BARRIERS\n")
    print("Running Stencil on " + str(CkNumPes()) + " processors with " + str((ro.num_chare_x, ro.num_chare_y, ro.num_chare_z)) + " chares")
    print("Array Dimensions: " + str((ro.arrayDimX, ro.arrayDimY, ro.arrayDimZ)))
    print("Block Dimensions: " + str((ro.blockDimX, ro.blockDimY, ro.blockDimZ)))

    # Create new array of worker chares
    ro.mainProxy = self.thisProxy
    self.array = Array(Stencil, (ro.num_chare_x, ro.num_chare_y, ro.num_chare_z))

    # Start the computation
    self.array.begin_iteration()

  def report(self):
    charm.printStats()
    charm.exit()

@numba.jit(nopython=True, cache=True)
def index(a,b,c,X,Y): return (a + b*(X+2) + c*(X+2)*(Y+2))

@numba.jit(nopython=True, cache=True)
def compute_kernel_fast(work, X, Y, Z, new_temperature, temperature):
  W = int(work)
  for k in range(1, Z+1):
    for j in range(1, Y+1):
      for i in range(1, X+1):
        # update my value based on the surrounding values
        for w in range(W):
          new_temperature[index(i, j, k, X, Y)] = (temperature[index(i-1, j, k, X, Y)] \
              +  temperature[index(i+1, j, k, X, Y)] \
              +  temperature[index(i, j-1, k, X, Y)] \
              +  temperature[index(i, j+1, k, X, Y)] \
              +  temperature[index(i, j, k-1, X, Y)] \
              +  temperature[index(i, j, k+1, X, Y)] \
              +  temperature[index(i, j, k, X, Y)] ) \
              *  DIVIDEBY7

@numba.jit(nopython=True, cache=True)
def constrainBC_fast(T,X,Y,Z):
  # Heat left, top and front faces of each chare's block
  for k in range(1,Z+1):
    for i in range(1,X+1):
      T[index(i, 1, k, X, Y)] = 255.0

  for k in range(1, Z+1):
    for j in range(1, Y+1):
      T[index(1, j, k, X, Y)] = 255.0

  for j in range(1, Y+1):
    for i in range(1, X+1):
      T[index(i, j, 1, X, Y)] = 255.0

@numba.jit(nopython=True, cache=True)
def fillGhostData(T, leftGhost, rightGhost, topGhost, bottomGhost, frontGhost, backGhost, blockDimX, blockDimY, blockDimZ):
  for k in range(blockDimZ):
    for j in range(blockDimY):
      leftGhost[k*blockDimY+j] = T[index(1, j+1, k+1, blockDimX, blockDimY)]
      rightGhost[k*blockDimY+j] = T[index(blockDimX, j+1, k+1, blockDimX, blockDimY)]

  for k in range(blockDimZ):
    for i in range(blockDimX):
      topGhost[k*blockDimX+i] = T[index(i+1, 1, k+1, blockDimX, blockDimY)]
      bottomGhost[k*blockDimX+i] = T[index(i+1, blockDimY, k+1, blockDimX, blockDimY)]

  for j in range(blockDimY):
    for i in range(blockDimX):
      frontGhost[j*blockDimX+i] = T[index(i+1, j+1, 1, blockDimX, blockDimY)];
      backGhost[j*blockDimX+i] = T[index(i+1, j+1, blockDimZ, blockDimX, blockDimY)]

@numba.jit(nopython=True, cache=True)
def processGhosts_fast(T, direction, width, height, gh, X, Y, Z):
  if direction == LEFT:
    for k in range(width):
      for j in range(height):
        T[index(0, j+1, k+1, X, Y)] = gh[k*height+j]
  elif direction == RIGHT:
    for k in range(width):
      for j in range(height):
        T[index(X+1, j+1, k+1, X, Y)] = gh[k*height+j]
  elif direction == BOTTOM:
    for k in range(width):
      for i in range(height):
        T[index(i+1, 0, k+1, X, Y)] = gh[k*height+i]
  elif direction == TOP:
    for k in range(width):
      for i in range(height):
        T[index(i+1, Y+1, k+1, X, Y)] = gh[k*height+i]
  elif direction == FRONT:
    for j in range(width):
      for i in range(height):
        T[index(i+1, j+1, 0, X, Y)] = gh[j*height+i]
  elif direction == BACK:
    for j in range(width):
      for i in range(height):
        T[index(i+1, j+1, Z+1, X, Y)] = gh[j*height+i]

class Stencil(Chare):
  def __init__(self):
    #print("Element " + str(self.thisIndex) + " created")

    arrSize = (ro.blockDimX+2) * (ro.blockDimY+2) * (ro.blockDimZ+2)
    if self.thisIndex == (0,0,0): print("array size=" + str(arrSize))
    self.temperature = np.zeros(arrSize)
    self.new_temperature = np.zeros(arrSize)
    self.iterations = 0
    self.msgsRcvd = 0
    constrainBC_fast(self.temperature,ro.blockDimX,ro.blockDimY,ro.blockDimZ)

    # start measuring time
    if self.thisIndex == (0,0,0): self.startTime = time.time()

  def begin_iteration(self):
    self.iterations += 1
    blockDimX, blockDimY, blockDimZ = ro.blockDimX, ro.blockDimY, ro.blockDimZ
    X,Y,Z = ro.blockDimX, ro.blockDimY, ro.blockDimZ

    # Copy different faces into messages
    leftGhost = np.zeros((blockDimY*blockDimZ))
    rightGhost = np.zeros((blockDimY*blockDimZ))
    topGhost = np.zeros((blockDimX*blockDimZ))
    bottomGhost = np.zeros((blockDimX*blockDimZ))
    frontGhost = np.zeros((blockDimX*blockDimY))
    backGhost = np.zeros((blockDimX*blockDimY))

    fillGhostData(self.temperature, leftGhost, rightGhost, topGhost, bottomGhost, frontGhost, backGhost, blockDimX, blockDimY, blockDimZ)
    X,Y,Z = ro.num_chare_x, ro.num_chare_y, ro.num_chare_z
    i = self.thisIndex

    # Send my left face
    self.thisProxy[(i[0]-1)%X, i[1], i[2]].receiveGhosts(self.iterations, RIGHT, blockDimY, blockDimZ, leftGhost)
    # Send my right face
    self.thisProxy[(i[0]+1)%X, i[1], i[2]].receiveGhosts(self.iterations, LEFT, blockDimY, blockDimZ, rightGhost)
    # Send my bottom face
    self.thisProxy[i[0], (i[1]-1)%Y, i[2]].receiveGhosts(self.iterations, TOP, blockDimX, blockDimZ, bottomGhost)
    # Send my top face
    self.thisProxy[i[0], (i[1]+1)%Y, i[2]].receiveGhosts(self.iterations, BOTTOM, blockDimX, blockDimZ, topGhost)
    # Send my front face
    self.thisProxy[i[0], i[1], (i[2]-1)%Z].receiveGhosts(self.iterations, BACK, blockDimX, blockDimY, frontGhost)
    # Send my back face
    self.thisProxy[i[0], i[1], (i[2]+1)%Z].receiveGhosts(self.iterations, FRONT, blockDimX, blockDimY, backGhost)

  @when("iterations")
  def receiveGhosts(self, iteration, direction, height, width, gh):
    self.processGhosts(direction, height, width, gh)
    self.msgsRcvd += 1
    if self.msgsRcvd == 6:
      self.msgsRcvd = 0
      self.thisProxy[self.thisIndex].check_and_compute()

  def processGhosts(self, direction, height, width, gh):
    blockDimX, blockDimY, blockDimZ = ro.blockDimX, ro.blockDimY, ro.blockDimZ
    processGhosts_fast(self.temperature, direction, width, height, gh, blockDimX, blockDimY, blockDimZ)

  def check_and_compute(self):
    self.compute_kernel()

    # calculate error
    # not being done right now since we are doing a fixed no. of iterations

    self.temperature,self.new_temperature = self.new_temperature,self.temperature

    constrainBC_fast(self.temperature,ro.blockDimX,ro.blockDimY,ro.blockDimZ)

    if self.thisIndex == (0,0,0):
      endTime = time.time()
      print("[" + str(self.iterations) + "] Time per iteration: " + str(endTime-self.startTime) + " " + str(endTime-ro.initTime))

    if self.iterations == MAX_ITER:
      self.contribute(None, None, ro.mainProxy.report)
    else:
      if self.thisIndex == (0,0,0): self.startTime = time.time()
      if self.iterations % LBPERIOD_ITER == 0:
        self.AtSync()
      else:
        self.contribute(None, None, self.thisProxy.begin_iteration)

  # Check to see if we have received all neighbor values yet
  # If all neighbor values have been received, we update our values and proceed
  def compute_kernel(self):
    itno = int(math.ceil(float(self.iterations)/CHANGELOAD)) * 5
    i = self.thisIndex
    X,Y,Z = ro.num_chare_x, ro.num_chare_y, ro.num_chare_z
    idx = i[0] + i[1]*X + i[2]*X*Y
    numChares = X * Y * Z
    work = 100.0

    if (idx >= numChares*0.2) and (idx <= numChares*0.8):
      work = work * (float(idx)/numChares) + float(itno)
    else:
      work = 10.0

    blockDimX, blockDimY, blockDimZ = ro.blockDimX, ro.blockDimY, ro.blockDimZ
    compute_kernel_fast(work, blockDimX, blockDimY, blockDimZ, self.new_temperature, self.temperature)

  def resumeFromSync(self):
    self.begin_iteration()

# ------ start charm -------

charm.start()
