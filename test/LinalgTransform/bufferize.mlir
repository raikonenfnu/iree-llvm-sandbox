// RUN: mlir-proto-opt -linalg-interp-transforms %s | FileCheck %s

// CHECK-LABEL: func @matmul_tensors(
// CHECK-SAME:    %[[TA:[0-9a-z]+]]: memref<128x128xf32
// CHECK-SAME:    %[[TB:[0-9a-z]+]]: memref<128x128xf32
// CHECK-SAME:    %[[TC:[0-9a-z]+]]: memref<128x128xf32
// CHECK-NOT:   -> tensor
func @matmul_tensors(
  %arg0: tensor<128x128xf32>, %arg1: tensor<128x128xf32>, %arg2: tensor<128x128xf32> { linalg.inplaceable = true})
    -> tensor<128x128xf32> {
  // CHECK: linalg.matmul ins(%[[TA]], %[[TB]] : memref{{.*}}, memref{{.*}} outs(%[[TC]] : memref{{.*}})
  %0 = linalg.matmul  ins(%arg0, %arg1: tensor<128x128xf32>, tensor<128x128xf32>)
                     outs(%arg2: tensor<128x128xf32>)
    -> tensor<128x128xf32>

  // CHECK: return
  // CHECK-NOT: %{{.*}}
  return %0 : tensor<128x128xf32>
// CHECK: }
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
  bufferize
}
