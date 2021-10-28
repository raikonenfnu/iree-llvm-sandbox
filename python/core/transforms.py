from mlir.ir import *
from mlir.passmanager import *

import mlir.all_passes_registration


class Transform:
  """Base class for all parametrized transformations."""

  def __call__(self, module: Module, fun_name: str):
    PassManager.parse(self.pipeline).run(module)
    return module


class Print(Transform):
  """Print intermediate IR.

  Dump the module and do not change it. The transform can be configured as
  follows:
  * `name`: Printer name.
  """

  def __init__(self, name=''):
    self.name = name

  def __call__(self, module: Module, fun_name: str):
    print('[[[ IR printer: ' + self.name + ' ]]]')
    module.dump()
    return module


class ExperimentalSplitAndFuseFillOp(Transform):
  """Tile and fuse FillOp into the output of reduction.

  This transform can be configured as follows:
  * `tile_sizes`: Tile sizes used for tiling.
  """

  def __init__(self, fun_name: str, op_name: str, tile_sizes=[]):
    if tile_sizes:
      tile_str = f'tile-sizes={",".join([str(ts) for ts in tile_sizes])}'
    pipeline = (f'linalg-tensor-codegen-driver{{'
                f'     anchor-func={fun_name} '
                f'     anchor-op={op_name} '
                f'     fuse-fill-into-reduction '
                f'     {tile_str}}},'
                f'canonicalize,'
                f'cse')
    self.pipeline = pipeline



class Inject(Transform):
  """Inject intermediate IR.

  Replace the module by the provided IR. The transform can be configured as
  follows:
  * `ir`: Textual IR to inject.
  """

  def __init__(self, ir: str):
    self.ir = ir

  def __call__(self, module: Module, fun_name: str):
    return Module.parse(self.ir)


class Fuse(Transform):
  """Tile a linalg op and fuse its producers.

  This transform can be configured as follows:
  * `tile_sizes`: Tile sizes used for tiling.
  * `tile_interchange`: Interchange used for tiling.
  """

  def __init__(self,
               fun_name: str,
               op_name: str,
               tile_sizes=[],
               tile_interchange=[],
               pad=False):
    tile_str = ''
    interchange_str = ''
    if tile_sizes:
      tile_str = f'tile-sizes={",".join([str(ts) for ts in tile_sizes])}'
    if tile_interchange:
      dims = [str(ic) for ic in tile_interchange]
      interchange_str = f'tile-interchange={",".join(dims)}'
    pipeline = (f'linalg-tensor-codegen-driver{{'
                f'     anchor-func={fun_name} '
                f'     anchor-op={op_name} '
                f'     fuse '
                f'     {tile_str} '
                f'     {interchange_str}}},'
                f'canonicalize,'
                f'cse')
    self.pipeline = pipeline


class Tile(Transform):
  """Tile a linalg op with `tile_sizes`.

  This transform can be configured as follows:
  * `tile_sizes`: Tile sizes used for tiling.
  * `tile_interchange`: Interchange used for tiling.
  * `peel`: Peel the specified loops generated by the tiling pattern. Cannot be
     used together with `pad`.
  * `pad`: Pad the specified operands.
  * `pack_padding`: Pack the specified operands into buffers. `pad` must also be
     specified.
  * `hoist_padding`: Hoist padding around the specified number of loops. `pad`
     must also be specified.
  * `scalarize_dyn_dims`: Scalarize all dimensions that having statically
    unknown size. Either `tile_sizes` or `scalarize_dyn_dims` must be specified.
    Cannot use both at the same time. Cannot be used together with `pad` or
    `peel`.
  """

  def __init__(self,
               fun_name: str,
               op_name: str,
               tile_sizes=[],
               tile_interchange=[],
               peel=[],
               pad=False,
               pack_padding=[],
               hoist_padding=[],
               scalarize_dyn_dims=False):
    tile_str = ''
    interchange_str = ''
    pad_str = ''
    hoist_padding_str = ''
    peeled_loops_str = ''
    scalarize_dyn_dims_str = ''

    if tile_sizes:
      tile_str = f'tile-sizes={",".join([str(ts) for ts in tile_sizes])}'
    if tile_interchange:
      dims = [str(ic) for ic in tile_interchange]
      interchange_str = f'tile-interchange={",".join(dims)}'
    if pad:
      nofold_indices = [str(pp) for pp in pack_padding]
      pad_str = (f'pad nofold-operands={",".join(nofold_indices)}'
                ) if len(nofold_indices) > 0 else 'pad'
    if hoist_padding:
      hoisting_depths = [str(hd) for hd in hoist_padding]
      hoist_padding_str = f'hoist-padding={",".join(hoisting_depths)}'
    if peel:
      loop_indices = [str(l) for l in peel]
      peeled_loops_str = f'peeled-loops={",".join(loop_indices)}'
    if scalarize_dyn_dims:
      scalarize_dyn_dims_str = 'scalarize-dynamic-dims'

    pipeline = (f'linalg-tensor-codegen-driver{{'
                f'     anchor-func={fun_name} '
                f'     anchor-op={op_name} '
                f'     {tile_str} '
                f'     {interchange_str} '
                f'     {peeled_loops_str} '
                f'     {scalarize_dyn_dims_str} '
                f'     {pad_str} '
                f'     {hoist_padding_str}}},'
                f'canonicalize,'
                f'cse')
    self.pipeline = pipeline


class Vectorize(Transform):

  def __init__(self, fun_name: str, op_name: str):
    pipeline = (f'linalg-tensor-codegen-driver{{'
                f'     anchor-func={fun_name} '
                f'     anchor-op={op_name} '
                f'     vectorize '
                f'     vectorize-padding}},'
                f'canonicalize,'
                f'cse')
    self.pipeline = pipeline


class Generalize(Transform):
  """Transform a named operation to its generic form.

  This transform can be configured as follows:
  * `iterator_interchange`: Interchange the iterators of the generic operation.

  Note: After generalization the anchor op name changes to 'linalg.generic'.
  """

  def __init__(self, fun_name: str, op_name: str, iterator_interchange=[]):
    interchange_str = ''

    if iterator_interchange:
      dims = [str(ic) for ic in iterator_interchange]
      interchange_str = f'iterator-interchange={",".join(dims)}'

    pipeline = (f'linalg-tensor-codegen-driver{{'
                f'     anchor-func={fun_name} '
                f'     anchor-op={op_name} '
                f'     generalize '
                f'     {interchange_str}}}')
    self.pipeline = pipeline


class Bufferize(Transform):

  def __init__(self):
    pipeline = (f'linalg-tensor-codegen-driver{{'
                f'     bufferize=true}},'
                f'canonicalize,'
                f'cse')
    self.pipeline = pipeline


class LowerVectors(Transform):

  def __init__(self, stage):
    pipeline = (f'linalg-tensor-codegen-driver{{'
                f'    lower-vector '
                f'    lower-vector-stage={stage}'
                f'    max-transfer-rank=1 '
                f'    split-transfers=linalg-copy '
                f'    lower-vector-transpose-to=eltwise '
                f'    lower-vector-multi-reduction-to=innerparallel '
                f'    lower-vector-contraction-to=outerproduct '
                f'    unroll-vector-transfers=true}},'
                f'canonicalize,'
                f'cse')
    self.pipeline = pipeline


class LowerToLLVM(Transform):

  def __init__(self):
    pipeline = (f'linalg-tensor-codegen-driver{{'
                f'    lower-to-llvm}},'
                f'canonicalize,'
                f'cse')
    self.pipeline = pipeline


class Sparsify(Transform):

  def __init__(self, options: str):
    pipeline = (
        f'sparsification{{{options}}},'
        f'sparse-tensor-conversion,'
        f'builtin.func(convert-linalg-to-loops,convert-vector-to-scf),'
        f'convert-scf-to-std,'
        f'func-bufferize,'
        f'tensor-constant-bufferize,'
        f'builtin.func(tensor-bufferize,std-bufferize,finalizing-bufferize),'
        f'convert-vector-to-llvm{{reassociate-fp-reductions=1 enable-index-optimizations=1}},'
        f'lower-affine,'
        f'convert-memref-to-llvm,'
        f'convert-std-to-llvm,'
        f'reconcile-unrealized-casts')
    self.pipeline = pipeline
