#  Part of the LLVM Project, under the Apache License v2.0 with LLVM Exceptions.
#  See https://llvm.org/LICENSE.txt for license information.
#  SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

try:
  import mlir.ir as ir
  from typing import Optional, Sequence, Union
except ImportError as e:
  raise RuntimeError("Error loading imports from extension module") from e

BoolArg = Optional[Union[bool, ir.BoolAttr]]
IntListArg = Optional[Union[Sequence[int], ir.ArrayAttr]]
StringArg = Optional[Union[str, ir.StringAttr]]


def _defaulted_ensure(f):

  def inner(value, default=None):
    assert value is not None or default is not None
    return f(default if value is None else value)

  return inner


@_defaulted_ensure
def _ensure_array_attr(value: IntListArg):
  i64 = ir.IntegerType.get_signless(64)
  if isinstance(value, Sequence):
    return ir.ArrayAttr.get([ir.IntegerAttr.get(i64, i) for i in value])
  return value


@_defaulted_ensure
def _ensure_bool_attr(value: BoolArg):
  if isinstance(value, bool):
    return ir.BoolAttr.get(value)
  return value


@_defaulted_ensure
def _ensure_string_attr(value: StringArg):
  if isinstance(value, str):
    return ir.StringAttr.get(value)
  return value


class LowerVectorsOp:
  """Specialization for the LowerVectorsOp class."""

  def __init__(self,
               *,
               stages: IntListArg = None,
               contraction_lowering: StringArg = None,
               multireduction_lowering: StringArg = None,
               transpose_lowering: StringArg = None,
               transpose_avx2_lowering: BoolArg = None,
               loc=None,
               ip=None):
    stages = _ensure_array_attr(stages, [0, 1, 2, 3, 4, 5, 6])
    contraction_lowering = _ensure_string_attr(contraction_lowering,
                                               "outerproduct")
    multireduction_lowering = _ensure_string_attr(multireduction_lowering,
                                                  "innerparallel")
    transpose_lowering = _ensure_string_attr(transpose_lowering, "eltwise")
    transpose_avx2_lowering = _ensure_bool_attr(transpose_avx2_lowering, False)

    super().__init__(stages,
                     contraction_lowering,
                     multireduction_lowering,
                     transpose_lowering,
                     transpose_avx2_lowering,
                     loc=loc,
                     ip=ip)


class TileOp:
  """Specialization for the TileOp class."""

  def __init__(self,
               target: Union[ir.Value, ir.Operation, ir.OpView, str,
                             ir.FlatSymbolRefAttr],
               *,
               sizes: IntListArg = None,
               interchange: IntListArg = None,
               pad: BoolArg = None,
               pack_paddings: IntListArg = None,
               hoist_paddings: IntListArg = None,
               scalarize_dyn_dims: BoolArg = None,
               generalize: BoolArg = None,
               loc=None,
               ip=None):
    sizes = _ensure_array_attr(sizes, [])
    interchange = _ensure_array_attr(interchange, [])
    pad = _ensure_bool_attr(pad, False)
    pack_paddings = _ensure_array_attr(pack_paddings, [])
    hoist_paddings = _ensure_array_attr(hoist_paddings, [])
    scalarize_dyn_dims = _ensure_bool_attr(scalarize_dyn_dims, False)
    generalize = _ensure_bool_attr(generalize, False)

    # FIXME: don't rely on parsing when the PDL dialect is available in Python
    operation_type = ir.Type.parse("!pdl.operation")

    if isinstance(target, str):
      target = ir.FlatSymbolRefAttr.get(target)

      super().__init__(
          operation_type,
          target if not isinstance(target, ir.FlatSymbolRefAttr) else None,
          target if isinstance(target, ir.FlatSymbolRefAttr) else None,
          sizes,
          interchange,
          pad,
          pack_paddings,
          hoist_paddings,
          scalarize_dyn_dims,
          generalize,
          loc=loc,
          ip=ip)
      return


class VectorizeOp:

  def __init__(self,
               target: Union[ir.Value, ir.Operation, ir.OpView, str,
                             ir.FlatSymbolRefAttr],
               *,
               vectorize_padding: BoolArg,
               loc=None,
               ip=None):
    if isinstance(target, str):
      target = ir.FlatSymbolRefAttr(target)

    # FIXME: don't rely on parsing when the PDL dialect is available in Python
    operation_type = ir.Type.parse("!pdl.operation")

    super().__init__(
        operation_type,
        target if not isinstance(target, ir.FlatSymbolRefAttr) else None,
        target if isinstance(target, ir.FlatSymbolRefAttr) else None,
        _ensure_bool_attr(vectorize_padding, False),
        loc=loc,
        ip=ip)


class SequenceOp:

  def __init__(self, *, loc=None, ip=None):
    super().__init__(loc=loc, ip=ip)
    self.body.blocks.append()
