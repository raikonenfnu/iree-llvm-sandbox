// RUN: mlir-proto-opt -linalg-transform-expert-expansion -split-input-file %s | FileCheck %s --check-prefix=EXPAND
// RUN: mlir-proto-opt -linalg-transform-expert-expansion -linalg-interp-transforms -split-input-file %s | FileCheck %s

// CHECK-LABEL: func @matmul_tensors
// CHECK-NOT: linalg
// CHECK: llvm
func @matmul_tensors(
  %arg0: tensor<128x128xf32>, %arg1: tensor<128x128xf32>, %arg2: tensor<128x128xf32> { linalg.inplaceable = true})
    -> tensor<128x128xf32> {
  %0 = linalg.matmul  ins(%arg0, %arg1: tensor<128x128xf32>, tensor<128x128xf32>)
                     outs(%arg2: tensor<128x128xf32>)
    -> tensor<128x128xf32>

  return %0 : tensor<128x128xf32>
}

pdl.pattern @pdl_target : benefit(1) {
  %args = pdl.operands
  %results = pdl.types
  %0 = pdl.operation "linalg.matmul"(%args : !pdl.range<value>) -> (%results : !pdl.range<type>)
  pdl.apply_native_constraint "nestedInFunc"[@matmul_tensors](%0 : !pdl.operation)
  // TODO: we don't want this, but it is the required terminator for pdl.pattern
  pdl.rewrite %0 with "linalg_transform.apply"
}

linalg_transform.sequence {
  // This should match the strategy below.
  // EXPAND-NOT: expert apply
  // EXPAND: %[[HANDLE:.*]] = tile when @pdl_target {sizes = [4, 4, 4]}
  // EXPAND: %[[HANDLE2:.*]] = vectorize %[[HANDLE]] {vectorize_padding = true}
  // EXPAND: bufferize
  // EXPAND: lower_vectors {multireduction_lowering = "innerreduce"}
  // EXPAND: lower_to_llvm
  expert apply "single_tiling" when @pdl_target
  {
    tile_sizes = [4, 4, 4],
    vectorize_padding = true,
    multireduction_lowering = "innerreduce"
  }
}

// CHECK-NOT: @strategies
// EXPAND-NOT: @strategies
module @strategies {
  pdl.pattern @single_tiling_matcher : benefit(1) {
    %tile_sizes = pdl.attribute
    %vectorize_padding = pdl.attribute
    %multireduction_lowering = pdl.attribute
    %name = pdl.attribute : "single_tiling"
    %target = pdl.attribute
    %transformed = pdl.type
    %root = pdl.operation "linalg_transform.expert" {
      "expertName" = %name,
      "targetMatcher" = %target,
      "tile_sizes" = %tile_sizes,
      "vectorize_padding" = %vectorize_padding,
      "multireduction_lowering" = %multireduction_lowering
    } -> (%transformed : !pdl.type)

    pdl.rewrite %root {
      %tile = pdl.operation "linalg_transform.tile"  {
        "targetMatcher" = %target,
        "sizes" = %tile_sizes
      } -> (%transformed : !pdl.type)
      %handle = pdl.result 0 of %tile

      %vectorize = pdl.operation "linalg_transform.vectorize"(%handle : !pdl.value) {
        "vectorize_padding" = %vectorize_padding
      } -> (%transformed : !pdl.type)
      %handle2 = pdl.result 0 of %vectorize

      // FIXME: must explicitly query results, otherwise the op is not produced
      %bufferize = pdl.operation "linalg_transform.bufferize"
      pdl.results of %bufferize

      // FIXME: must explicitly query results, otherwise the op is not produced
      %lower_vectors = pdl.operation "linalg_transform.lower_vectors" {
        "multireduction_lowering" = %multireduction_lowering
      }
      pdl.results of %lower_vectors

      // FIXME: must explicitly query results, otherwise the op is not produced
      %lower_to_llvm = pdl.operation "linalg_transform.lower_to_llvm"
      pdl.results of %lower_to_llvm

      pdl.replace %root with (%handle2 : !pdl.value)
    }
  }
}

// -----

// CHECK-LABEL: func @matmul_tensors2
// CHECK-NOT: linalg
// CHECK: llvm
func @matmul_tensors2(
  %arg0: tensor<128x128xf32>, %arg1: tensor<128x128xf32>, %arg2: tensor<128x128xf32> { linalg.inplaceable = true})
    -> tensor<128x128xf32> {
  %0 = linalg.matmul  ins(%arg0, %arg1: tensor<128x128xf32>, tensor<128x128xf32>)
                     outs(%arg2: tensor<128x128xf32>)
    -> tensor<128x128xf32>

  return %0 : tensor<128x128xf32>
}

pdl.pattern @pdl_target2 : benefit(1) {
  %args = pdl.operands
  %results = pdl.types
  %0 = pdl.operation "linalg.matmul"(%args : !pdl.range<value>) -> (%results : !pdl.range<type>)
  pdl.apply_native_constraint "nestedInFunc"[@matmul_tensors2](%0 : !pdl.operation)
  // TODO: we don't want this, but it is the required terminator for pdl.pattern
  pdl.rewrite %0 with "linalg_transform.apply"
}

linalg_transform.sequence {
  // This should match the strategy below.
  // EXPAND-NOT: expert apply
  // EXPAND: %[[HANDLE:.*]] = tile when @pdl_target2 {sizes = [32, 8, 8]}
  // EXPAND: %[[HANDLE2:.*]] = tile %[[HANDLE]] {sizes = [4, 4, 4]}
  // EXPAND: %[[HANDLE3:.*]] = vectorize %[[HANDLE2]] {vectorize_padding = false}
  // EXPAND: bufferize
  // EXPAND: lower_vectors {multireduction_lowering = "innerparallel"}
  // EXPAND: lower_to_llvm
  %0 = tile when @pdl_target2 {sizes = [32, 8, 8]}
  expert apply "single_tiling" to %0
  {
    tile_sizes = [4, 4, 4],
    vectorize_padding = false,
    multireduction_lowering = "innerparallel"
  }
}

module @strategies {
  pdl.pattern @single_tiling_operand : benefit(1) {
    %tile_sizes = pdl.attribute
    %vectorize_padding = pdl.attribute
    %multireduction_lowering = pdl.attribute
    %name = pdl.attribute : "single_tiling"
    %type = pdl.type : !pdl.operation
    %target = pdl.operand : %type
    %transformed = pdl.type
    %root = pdl.operation "linalg_transform.expert"(%target : !pdl.value) {
      "expertName" = %name,
      "tile_sizes" = %tile_sizes,
      "vectorize_padding" = %vectorize_padding,
      "multireduction_lowering" = %multireduction_lowering
    } -> (%transformed : !pdl.type)

    pdl.rewrite %root {
      %tile = pdl.operation "linalg_transform.tile"(%target : !pdl.value)  {
        "sizes" = %tile_sizes
      } -> (%transformed : !pdl.type)
      %handle = pdl.result 0 of %tile

      %vectorize = pdl.operation "linalg_transform.vectorize"(%handle : !pdl.value) {
        "vectorize_padding" = %vectorize_padding
      } -> (%transformed : !pdl.type)
      %handle2 = pdl.result 0 of %vectorize

      // FIXME: must explicitly query results, otherwise the op is not produced
      %bufferize = pdl.operation "linalg_transform.bufferize"
      pdl.results of %bufferize

      // FIXME: must explicitly query results, otherwise the op is not produced
      %lower_vectors = pdl.operation "linalg_transform.lower_vectors" {
        "multireduction_lowering" = %multireduction_lowering
      }
      pdl.results of %lower_vectors

      // FIXME: must explicitly query results, otherwise the op is not produced
      %lower_to_llvm = pdl.operation "linalg_transform.lower_to_llvm"
      pdl.results of %lower_to_llvm

      pdl.replace %root with (%handle2 : !pdl.value)
    }
  }
}
