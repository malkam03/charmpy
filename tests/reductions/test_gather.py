from charmpy import charm, Chare, Mainchare, Array, Group, CkMyPe, CkNumPes, CkExit, CkAbort
from charmpy import readonlies as ro
from charmpy import Reducer

class Main(Mainchare):
  def __init__(self, args):

    self.recvdReductions = 0
    self.expectedReductions = 4

    ro.nDims = 1
    ro.ARRAY_SIZE = [10] * ro.nDims
    ro.firstIdx = [0] * ro.nDims
    ro.lastIdx = tuple([x-1 for x in ro.ARRAY_SIZE])

    self.nElements = 1
    for x in ro.ARRAY_SIZE: self.nElements *= x
    print("Running gather example on " + str(CkNumPes()) + " processors for " + str(self.nElements) + " elements, array dims=" + str(ro.ARRAY_SIZE))
    ro.mainProxy = self.thisProxy
    ro.arrProxy = Array(Test, ro.ARRAY_SIZE)
    ro.grpProxy = Group(TestGroup)
    ro.arrProxy.doGather()
    ro.grpProxy.doGather()

  def done_gather_single(self, result):
    gather_arr_indices = list(range(self.nElements))
    gather_grp_indices = list(range(CkNumPes()))
    assert result == gather_arr_indices or result == gather_grp_indices, "Gather single elements failed."
    print("[Main] Gather collective for single elements done. Test passed")
    self.recvdReductions += 1
    if (self.recvdReductions >= self.expectedReductions):
      CkExit()

  def done_gather_array(self, result):
    gather_arr_indices = [tuple([i]) for i in range(self.nElements)]
    gather_grp_indices = [[i, 42] for i in range(CkNumPes())]
    assert result == gather_arr_indices or result == gather_grp_indices, "Gather arrays failed."
    print("[Main] Gather collective for arrays done. Test passed")
    self.recvdReductions += 1
    if (self.recvdReductions >= self.expectedReductions):
      CkExit()

class Test(Chare):
  def __init__(self):
    print("Test " + str(self.thisIndex) + " created on PE " + str(CkMyPe()))

  def doGather(self):
    # gather single elements
    self.gather(self.thisIndex[0], ro.mainProxy.done_gather_single)
    # gather arrays
    self.gather(self.thisIndex, ro.mainProxy.done_gather_array)

class TestGroup(Chare):
  def __init__(self):
    print("TestGroup " + str(self.thisIndex) + " created on PE " + str(CkMyPe()))

  def doGather(self):
    # gather single elements
    self.gather(self.thisIndex, ro.mainProxy.done_gather_single)
    # gather arrays
    self.gather([self.thisIndex, 42], ro.mainProxy.done_gather_array)



# ---- start charm ----
charm.start()
