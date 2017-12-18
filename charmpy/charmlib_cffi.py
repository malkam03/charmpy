from _charmlib import ffi, lib
import sys
import time
if sys.version_info[0] < 3:
  import cPickle
else:
  import pickle as cPickle

index_ctype = ('', 'int[1]', 'int[2]', 'int[3]', 'short[4]', 'short[5]', 'short[6]')

class ContributeInfo:
  def __init__(self, args):
    # Need to save these cdata objects or they will be deleted. Simply putting them
    # in the 'struct ContributeInfo' is not enough
    self.c_data = args[1]
    self.dataSize = args[3]
    self.c_idx  = args[6]
    # TODO: have this struct always pre-allocated? currently ContributeInfo is used
    # and discarded right after call to 'getContributeInfo' so it should be safe
    self.data = ffi.new("struct ContributeInfo*", args)

class CharmLib(object):

  def __init__(self, _charm, opts, libcharm_path):
    global charm, ReducerType, ReducerTypeMap, times
    charm = _charm
    self.name = 'cffi'
    self.chareNames = []
    self.init()
    ReducerType = ffi.cast('struct CkReductionTypesExt*', lib.getReducersStruct())
    ReducerTypeMap = self.buildReducerTypeMap(ReducerType)
    self.ReducerType = ReducerType
    self.ReducerTypeMap = ReducerTypeMap
    times = [0.0] * 3 # track time in [charm reduction callbacks, custom reduction, outgoing object migration]
    self.times = times

  def buildReducerTypeMap(self, r):
    fields = [f for (f,t) in ffi.typeof("struct CkReductionTypesExt").fields]
    R = [None] * (max([getattr(r, f) for f in fields]) + 1)
    # update this function as and when new reducer types are added to CharmPy
    R[r.sum_int] = ('int', 'int[]', 'int*', ffi.sizeof('int'))
    R[r.sum_float] = ('float', 'float[]', 'float*', ffi.sizeof('float'))
    R[r.sum_double] = ('double', 'double[]', 'double*', ffi.sizeof('double'))
    R[r.nop] = (None, None, None, 0)
    R[r.max_int] = ('int', 'int[]', 'int*', ffi.sizeof('int'))
    R[r.max_float] = ('float', 'float[]', 'float*', ffi.sizeof('float'))
    R[r.max_double] = ('double', 'double[]', 'double*', ffi.sizeof('double'))
    R[r.external_py] = ('char', 'char[]', 'char*', ffi.sizeof('char'))
    return R

  def getContributeInfo(self, ep, data, reducer_type, contributor):
    numElems = len(data)
    if reducer_type == self.ReducerType.external_py:
      c_data = ffi.from_buffer(data)  # this avoids a copy
      c_data_size = numElems * ffi.sizeof('char')
    elif reducer_type != self.ReducerType.nop:
      dataTypeTuple = self.ReducerTypeMap[reducer_type]
      # TODO avoid copy if data is a buffer-type object, but not sure if that would
      # work with charm internal reductions. Example: dealing with numpy datatypes
      c_data = ffi.new(dataTypeTuple[1], data)
      c_data_size = numElems * dataTypeTuple[3]
    else:
      c_data = ffi.NULL
      c_data_size = 0

    elemId, index, elemType = contributor
    if type(index) == int: index = (index,)
    c_elemIdx = ffi.new('int[]', index)
    return ContributeInfo((ep, c_data, numElems, c_data_size, reducer_type, elemId,
                          c_elemIdx, len(index), elemType))
#    return ffi.new("struct ContributeInfo*", (ep, c_data, numElems, c_data_size, reducer_type, elemId,
#                          c_elemIdx, len(index), elemType))

  @ffi.def_extern()
  def recvReadOnly_py2(msgSize, msg):
    try:
      charm.recvReadOnly(ffi.buffer(msg, msgSize)[:])
    except:
      charm.handleGeneralError()

  @ffi.def_extern()
  def recvReadOnly_py3(msgSize, msg):
    try:
      charm.recvReadOnly(ffi.buffer(msg, msgSize))
    except:
      charm.handleGeneralError()

  @ffi.def_extern()
  def buildMainchare(onPe, objPtr, ep, argc, argv):
    try:
      objPtr = int(ffi.cast("uintptr_t", objPtr))
      charm.buildMainchare(onPe, objPtr, ep, [ffi.string(argv[i]) for i in range(argc)])
    except:
      charm.handleGeneralError()

  @ffi.def_extern()
  def recvChareMsg_py2(onPe, objPtr, ep, msgSize, msg):
    try:
      t0 = None
      if charm.opts.PROFILING: t0 = time.time()
      objPtr = int(ffi.cast("uintptr_t", objPtr))
      charm.recvChareMsg(onPe, objPtr, ep, ffi.buffer(msg, msgSize)[:], t0)
    except:
      charm.handleGeneralError()

  @ffi.def_extern()
  def recvChareMsg_py3(onPe, objPtr, ep, msgSize, msg):
    try:
      t0 = None
      if charm.opts.PROFILING: t0 = time.time()
      objPtr = int(ffi.cast("uintptr_t", objPtr))
      charm.recvChareMsg(onPe, objPtr, ep, ffi.buffer(msg, msgSize), t0)
    except:
      charm.handleGeneralError()

  @ffi.def_extern()
  def recvGroupMsg_py2(gid, ep, msgSize, msg):
    try:
      t0 = None
      if charm.opts.PROFILING: t0 = time.time()
      charm.recvGroupMsg(gid, ep, ffi.buffer(msg, msgSize)[:], t0)
    except:
      charm.handleGeneralError()

  @ffi.def_extern()
  def recvGroupMsg_py3(gid, ep, msgSize, msg):
    try:
      t0 = None
      if charm.opts.PROFILING: t0 = time.time()
      charm.recvGroupMsg(gid, ep, ffi.buffer(msg, msgSize), t0)
    except:
      charm.handleGeneralError()

  @ffi.def_extern()
  def recvArrayMsg_py2(aid, ndims, arrayIndex, ep, msgSize, msg):
    try:
      t0 = None
      if charm.opts.PROFILING: t0 = time.time()
      arrIndex = tuple(ffi.cast(index_ctype[ndims], arrayIndex))
      charm.recvArrayMsg(aid, arrIndex, ep, ffi.buffer(msg, msgSize)[:], t0)
    except:
      charm.handleGeneralError()

  @ffi.def_extern()
  def recvArrayMsg_py3(aid, ndims, arrayIndex, ep, msgSize, msg):
    try:
      t0 = None
      if charm.opts.PROFILING: t0 = time.time()
      arrIndex = tuple(ffi.cast(index_ctype[ndims], arrayIndex))
      charm.recvArrayMsg(aid, arrIndex, ep, ffi.buffer(msg, msgSize), t0)
    except:
      charm.handleGeneralError()

  def CkChareSend(self, chare_id, ep, msg):
    objPtr = ffi.cast("void*", chare_id[1])
    lib.CkChareExtSend(chare_id[0], objPtr, ep, msg, len(msg))

  def CkGroupSend(self, group_id, index, ep, msg):
    lib.CkGroupExtSend(group_id, index, ep, msg, len(msg))

  def CkArraySend(self, array_id, index, ep, msg):
    lib.CkArrayExtSend(array_id, index, len(index), ep, msg, len(msg))

  def CkRegisterReadonly(self, n1, n2, msg):
    if msg is None: lib.CkRegisterReadonlyExt(n1, n2, 0, ffi.NULL)
    else: lib.CkRegisterReadonlyExt(n1, n2, len(msg), msg)

  def CkRegisterMainchare(self, name, numEntryMethods):
    self.chareNames.append(ffi.new("char[]", name.encode()))
    chareIdx, startEpIdx = ffi.new("int*"), ffi.new("int*")
    lib.CkRegisterMainChareExt(self.chareNames[-1], numEntryMethods, chareIdx, startEpIdx)
    return chareIdx[0], startEpIdx[0]

  def CkRegisterGroup(self, name, numEntryMethods):
    self.chareNames.append(ffi.new("char[]", name.encode()))
    chareIdx, startEpIdx = ffi.new("int*"), ffi.new("int*")
    lib.CkRegisterGroupExt(self.chareNames[-1], numEntryMethods, chareIdx, startEpIdx)
    return chareIdx[0], startEpIdx[0]

  def CkRegisterArray(self, name, numEntryMethods):
    self.chareNames.append(ffi.new("char[]", name.encode()))
    chareIdx, startEpIdx = ffi.new("int*"), ffi.new("int*")
    lib.CkRegisterArrayExt(self.chareNames[-1], numEntryMethods, chareIdx, startEpIdx)
    return chareIdx[0], startEpIdx[0]

  def CkCreateGroup(self, chareIdx, epIdx):
    return lib.CkCreateGroupExt(chareIdx, epIdx, ffi.NULL, 0)

  def CkCreateArray(self, chareIdx, dims, epIdx):
    return lib.CkCreateArrayExt(chareIdx, len(dims), dims, epIdx, ffi.NULL, 0)

  def start(self):
    argv_bufs = [ffi.new("char[]", arg.encode()) for arg in sys.argv]
    lib.StartCharmExt(len(sys.argv), argv_bufs)

  @ffi.def_extern()
  def arrayElemLeave(aid, ndims, arrayIndex, pdata, sizing):
    try:
      if charm.opts.PROFILING: t0 = time.time()
      arrIndex = tuple(ffi.cast(index_ctype[ndims], arrayIndex))
      msg = charm.arrayElemLeave(aid, arrIndex, bool(sizing))
      if sizing:
        pdata[0] = ffi.NULL
      else:
        CharmLib.tempData = msg # save msg, else it might be deleted before returning control to libcharm
        pdata[0] = ffi.from_buffer(CharmLib.tempData)
      if charm.opts.PROFILING:
        global times
        times[2] += (time.time() - t0)
      return len(msg)
    except:
      charm.handleGeneralError()

  @ffi.def_extern()
  def arrayElemJoin_py2(aid, ndims, arrayIndex, ep, msg, msgSize):
    try:
      t0 = None
      if charm.opts.PROFILING: t0 = time.time()
      arrIndex = tuple(ffi.cast(index_ctype[ndims], arrayIndex))
      charm.recvArrayMsg(aid, arrIndex, ep, ffi.buffer(msg, msgSize)[:], t0, migration=True)
    except:
      charm.handleGeneralError()

  @ffi.def_extern()
  def arrayElemJoin_py3(aid, ndims, arrayIndex, ep, msg, msgSize):
    try:
      t0 = None
      if charm.opts.PROFILING: t0 = time.time()
      arrIndex = tuple(ffi.cast(index_ctype[ndims], arrayIndex))
      charm.recvArrayMsg(aid, arrIndex, ep, ffi.buffer(msg, msgSize), t0, migration=True)
    except:
      charm.handleGeneralError()

  @ffi.def_extern()
  def resumeFromSync(aid, ndims, arrayIndex):
    try:
      t0 = None
      if charm.opts.PROFILING: t0 = time.time()
      arrIndex = tuple(ffi.cast(index_ctype[ndims], arrayIndex))
      charm.recvArrayMsg(aid, arrIndex, -1, None, t0, resumeFromSync=True)
    except:
      charm.handleGeneralError()

  def CkContributeToChare(self, contributeInfo, cid):
    objPtr = ffi.cast("void*", cid[1])
    lib.CkExtContributeToChare(contributeInfo.data, cid[0], objPtr)

  def CkContributeToGroup(self, contributeInfo, gid, elemIdx):
    lib.CkExtContributeToGroup(contributeInfo.data, gid, elemIdx)

  def CkContributeToArray(self, contributeInfo, aid, index):
    lib.CkExtContributeToArray(contributeInfo.data, aid, index, len(index))

  # Notes: data is a void*, it must be type casted based on reducerType to Python type
  # returnBuffer must contain the cPickled form of type casted data, use char** to writeback
  @ffi.def_extern()
  def cpickleData(data, returnBuffer, dataSize, reducerType):
    try:
      if charm.opts.PROFILING: t0 = time.time()
      pyData = []
      if reducerType != ReducerType.nop:
        dataTypeTuple = ReducerTypeMap[reducerType]
        numElems = dataSize // dataTypeTuple[3]
        #pyData = ffi.cast(dataTypeTuple[0] + '[' + str(int(numElems)) + ']', data)
        pyData = [ffi.unpack(ffi.cast(dataTypeTuple[2],data), numElems)]
        # if reduction result is one element, use base type
        if numElems == 1: pyData = pyData[0]

      msg = ({}, pyData) # first element is msg header
      # save msg, else it might be deleted before returning control to libcharm
      CharmLib.tempData = cPickle.dumps(msg, charm.opts.PICKLE_PROTOCOL)
      returnBuffer[0] = ffi.from_buffer(CharmLib.tempData)

      if charm.opts.PROFILING:
        global times
        times[0] += (time.time() - t0)

      return len(CharmLib.tempData)
    except:
      charm.handleGeneralError()

  # callback function invoked by Charm++ for reducing contributions using a Python reducer (built-in or custom)
  @ffi.def_extern()
  def pyReduction_py2(msgs, msgSizes, nMsgs, returnBuffer):
    try:
      if charm.opts.PROFILING: t0 = time.time()
      contribs = []
      currentReducer = None
      for i in range(nMsgs):
        msgSize = msgSizes[i]
        if msgSize > 0:
          header, args = cPickle.loads(ffi.buffer(msgs[i], msgSize)[:])
          customReducer = header[b"custom_reducer"]
          if currentReducer is None: currentReducer = customReducer
          # check for correctness of msg
          assert customReducer == currentReducer
          contribs.append(args[0])

      reductionResult = getattr(charm.Reducer, currentReducer)(contribs)
      rednMsg = ({b"custom_reducer": currentReducer}, [reductionResult])
      CharmLib.tempData = cPickle.dumps(rednMsg, charm.opts.PICKLE_PROTOCOL)
      returnBuffer[0] = ffi.from_buffer(CharmLib.tempData)

      if charm.opts.PROFILING:
        global times
        times[1] += (time.time() - t0)

      return len(CharmLib.tempData)
    except:
      charm.handleGeneralError()

  # callback function invoked by Charm++ for reducing contributions using a Python reducer (built-in or custom)
  @ffi.def_extern()
  def pyReduction_py3(msgs, msgSizes, nMsgs, returnBuffer):
    try:
      if charm.opts.PROFILING: t0 = time.time()
      contribs = []
      currentReducer = None
      for i in range(nMsgs):
        msgSize = msgSizes[i]
        if msgSize > 0:
          header, args = cPickle.loads(ffi.buffer(msgs[i], msgSize))
          customReducer = header[b"custom_reducer"]
          if currentReducer is None: currentReducer = customReducer
          # check for correctness of msg
          assert customReducer == currentReducer
          contribs.append(args[0])

      reductionResult = getattr(charm.Reducer, currentReducer)(contribs)
      rednMsg = ({b"custom_reducer": currentReducer}, [reductionResult])
      CharmLib.tempData = cPickle.dumps(rednMsg, charm.opts.PICKLE_PROTOCOL)
      returnBuffer[0] = ffi.from_buffer(CharmLib.tempData)

      if charm.opts.PROFILING:
        global times
        times[1] += (time.time() - t0)

      return len(CharmLib.tempData)
    except:
      charm.handleGeneralError()

  # first callback from Charm++ shared library
  @ffi.def_extern()
  def registerMainModule():
    try:
      charm.registerMainModule()
    except:
      charm.handleGeneralError()

  def init(self):

    lib.registerCkRegisterMainModuleCallback(lib.registerMainModule)
    lib.registerMainchareCtorExtCallback(lib.buildMainchare)
    lib.registerArrayElemLeaveExtCallback(lib.arrayElemLeave)
    lib.registerArrayResumeFromSyncExtCallback(lib.resumeFromSync)
    lib.registerCPickleDataExtCallback(lib.cpickleData)
    if sys.version_info[0] < 3:
      lib.registerReadOnlyRecvExtCallback(lib.recvReadOnly_py2)
      lib.registerChareMsgRecvExtCallback(lib.recvChareMsg_py2)
      lib.registerGroupMsgRecvExtCallback(lib.recvGroupMsg_py2)
      lib.registerArrayMsgRecvExtCallback(lib.recvArrayMsg_py2)
      lib.registerArrayElemJoinExtCallback(lib.arrayElemJoin_py2)
      lib.registerPyReductionExtCallback(lib.pyReduction_py2)
    else:
      lib.registerReadOnlyRecvExtCallback(lib.recvReadOnly_py3)
      lib.registerChareMsgRecvExtCallback(lib.recvChareMsg_py3)
      lib.registerGroupMsgRecvExtCallback(lib.recvGroupMsg_py3)
      lib.registerArrayMsgRecvExtCallback(lib.recvArrayMsg_py3)
      lib.registerArrayElemJoinExtCallback(lib.arrayElemJoin_py3)
      lib.registerPyReductionExtCallback(lib.pyReduction_py3)

    self.CkArrayExtSend = lib.CkArrayExtSend
    self.CkGroupExtSend = lib.CkGroupExtSend
    self.CkChareExtSend = lib.CkChareExtSend

    self.CkMyPe = lib.CkMyPeHook
    self.CkNumPes = lib.CkNumPesHook
    self.CkExit = lib.CkExit

  def CkAbort(self, msg):
    lib.CmiAbort(msg.encode())