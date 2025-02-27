#!/usr/bin/env python
# Script to run tests and benchmarks.
import argparse
import glob
import os
import re
import subprocess
import sys

import matplotlib
import seaborn
import pandas

from typing import Any, Mapping, Sequence


# Experimental setup.
experiments = {
  "matmul" : {
    "module" : "python.examples.matmul.bench",
    "arguments" : {
      "n_iters" : 100,
      "expert_list" : ["SingleTiling2D", "DoubleTileAndDecompose2D"],
      "problem_sizes_list" : [
        "18,32,96", "24,64,96", "48,64,128", "480,512,16", "384,256,256",
        "480,512,256", "784,128,512", "1020,1152,1152", "1920,2304,2304",
        "2304,2304,2560"
      ],
      "spec_list" : ["mk,kn"],
      "dynamic_at_compile_time_list": ["[]"]
    }
  },
  "conv_1d" : {
    "module" : "python.examples.conv.conv_1d_bench",
    "arguments" : {
      "n_iters" : 100,
      "problem_sizes_list" : [
        "8,256,32,3,64,[1],[1]", "8,256,32,3,64,[2],[2]",
        "8,988,32,3,64,[1],[1]", "8,988,32,3,64,[2],[2]",
        "8,4144,32,3,64,[1],[1]", "8,4144,32,3,64,[2],[2]",
        "8,11300,32,3,64,[1],[1]", "8,11300,32,3,64,[2],[2]"
      ],
    }
  },
  "conv_2d" : {
    "module" : "python.examples.conv.conv_2d_bench",
    "arguments" : {
      "n_iters" : 100,
      "problem_sizes_list" : [
        "8,16,16,32,3,3,64,[1,1],[1,1]", "8,16,16,32,3,3,64,[2,2],[2,2]",
        "8,26,38,32,3,3,64,[1,1],[1,1]", "8,26,38,32,3,3,64,[2,2],[2,2]",
        "8,56,74,32,3,3,64,[1,1],[1,1]", "8,56,74,32,3,3,64,[2,2],[2,2]",
        "8,100,113,32,3,3,64,[1,1],[1,1]", "8,100,113,32,3,3,64,[2,2],[2,2]"
      ],
    }
  },
  "depthwise_conv_1d" : {
    "module" : "python.examples.depthwise_conv.depthwise_conv_1d_bench",
    "arguments" : {
      "n_iters" : 100,
      "problem_sizes_list" : [
        "8,256,32,3,[1],[1]", "8,256,32,3,[2],[2]",
        "8,988,32,3,[1],[1]", "8,988,32,3,[2],[2]",
        "8,4144,32,3,[1],[1]", "8,4144,32,3,[2],[2]",
        "8,11300,32,3,[1],[1]", "8,11300,32,3,[2],[2]"
      ],
    }
  },
  "depthwise_conv_2d" : {
    "module" : "python.examples.depthwise_conv.depthwise_conv_2d_bench",
    "arguments" : {
      "n_iters" : 100,
      "problem_sizes_list" : [
        "8,16,16,32,3,3,[1,1],[1,1]", "8,16,16,32,3,3,[2,2],[2,2]",
        "8,26,38,32,3,3,[1,1],[1,1]", "8,26,38,32,3,3,[2,2],[2,2]",
        "8,56,74,32,3,3,[1,1],[1,1]", "8,56,74,32,3,3,[2,2],[2,2]",
        "8,100,113,32,3,3,[1,1],[1,1]", "8,100,113,32,3,3,[2,2],[2,2]"
      ],
    }
  },
  "row_reduction_2d" : {
    "module" : "python.examples.reduction.row_reduction_2d_bench",
    "arguments" : {
      "n_iters" : 100,
      "problem_sizes_list" : [
        "100,256",
        "200,512",
        "500,512",
        "500,1024",
        "1000,1024",
        "4000,6144",
        "8000,6144"
      ],
    }
  },
  "column_reduction_2d" : {
    "module" : "python.examples.reduction.column_reduction_2d_bench",
    "arguments" : {
      "n_iters" : 100,
      "problem_sizes_list" : [
        "100,256",
        "200,512",
        "500,512",
        "500,1024",
        "1000,1024",
        "4000,6144",
        "8000,6144"
      ],
    }
  },
  "transpose_2d" : {
    "module" : "python.examples.transpose.transpose_2d_bench",
    "arguments" : {
      "n_iters" : 100,
      "problem_sizes_list" : [
        "260,280", "270,280", "280,280", "300,280", "256,280",
        "260,256", "270,256", "280,256", "300,256", "256,256",
        "580,520", "570,520", "520,520", "660,520", "512,520",
        "580,512", "570,512", "520,512", "660,512", "512,512",
        "1100,1160", "1050,1160", "1160,1160", "1020,1160", "1040,1160",
        "1100,1024", "1050,1024", "1160,1024", "1020,1024", "1040,1024"
      ],
    }
  },
}


def _compress_problem_sizes_label(
            labels: Sequence[str]) -> (Sequence[str], Sequence[str]):
  """Shorten the problem size lables by removing redundant information.

  Plotting the entire problem size configuration for every axis tick
  requires a lot of space and results in overlapping labels. The method
  identifies the dimensions that take different values and filters out
  the dimensions that are constant for the entire plot. Additionally,
  the dimension names (it suffices to plot them once) and sizes values
  are returned seperately.

  Example:
  ["H=64,W=32", "H=64,W=64"]
  ->
  ["W"], ["32", "64"]
  """
  label_dicts = []
  for label in labels:
    groups = re.findall(r"""([a-zA-Z]+)=(\d+|\[[0-9, ]+\])""", label)
    label_dicts.append(dict(groups))
  # Collect all values for a specific key.
  value_dict = {}
  for label_dict in label_dicts:
    for k, v in label_dict.items():
      if k in value_dict:
        value_dict[k].add(v)
      else:
        value_dict[k] = set([v])
  # Collect the keys that have multiple values.
  keys = []
  for k, v in value_dict.items():
    if len(v) != 1:
      keys.append(k)
  # Collect the keys for every label
  new_labels = []
  for label_dict in label_dicts:
    new_labels.append(",".join([label_dict[k] for k in keys]))
  return keys, new_labels


def _plot_data(config_key_to_plot: str,
            data_key: str, data_label: str,
            data_to_plot: pandas.DataFrame,
            peak_value: int, peak_label: str) -> matplotlib.axes.Axes:
  """Plot the provided data and configuration combination."""
  plt = seaborn.violinplot(
      x=config_key_to_plot, y=data_key, data=data_to_plot)
  keys, new_labels = _compress_problem_sizes_label(
      [text.get_text() for text in plt.xaxis.get_ticklabels()])
  plt.set(xticklabels=new_labels)
  plt.set(xlabel=str.format(
      f"Problem Sizes [{','.join(keys)}]"), ylabel=data_label)
  plt.set(ylim=(0, round(1.02 * peak_value)))
  roofline = plt.axhline(y=peak_value)
  plt.text(-.4, peak_value * 0.99, peak_label,
           horizontalalignment="left", verticalalignment="top",
           color=roofline.get_color(), fontsize=9)
  plt.tick_params(axis="x", rotation=20)
  return plt


def _get_data_to_plot(data: pandas.DataFrame,
          plot_configuration: Mapping[str, str]) -> pandas.DataFrame:
  """Return the data points for the given plot configuration."""
  data_to_plot = data.copy()
  for k, v in plot_configuration.items():
    data_to_plot = data_to_plot[data_to_plot[k] == v]
  return data_to_plot


def _get_plot_file_name(plot_name: str,
            plot_configuration: Mapping[str, str]) -> str:
  """"Return unique file name for the plot configuration.

  Concat the plot configuration key value pairs and remove special
  characters that may not be supported by the file system.

  Example:
  {'expert': 'SingleTilingExpert', 'np_types': 'float32,float32,float32'}
  ->
  'plot_name_expert_SingleTilingExpert_np_types_float32float32float32.pdf'
  """
  file_name = plot_name
  for k, v in plot_configuration.items():
    alphanumeric = "".join([c for c in v if c.isalnum()])
    file_name += str.format(f"_{k}_{alphanumeric}")
  file_name += ".pdf"
  return file_name


def _plot_quantity(plot_name: str, path: os.path, data: pandas.DataFrame,
                   data_key: str, data_label: str,
                   peak_value: int, peak_label: str):
  """Plot the provided quantity for all problem sizes.

  Plot the problem sizes for every expert, np_types, etc. combination.
  """
  config_key_to_plot = "runtime_problem_sizes_dict"
  config_keys_to_fix = ["expert", "np_types", "dynamic_at_compile_time"]
  plot_configurations = data[config_keys_to_fix].drop_duplicates()
  # Create a plot for every combination of expert, np_types, etc.
  for _, plot_configuration in plot_configurations.iterrows():
    data_to_plot = _get_data_to_plot(data, plot_configuration.to_dict())
    # Plot the selected data.
    plt = _plot_data(config_key_to_plot, data_key,
                     data_label, data_to_plot, peak_value, peak_label)
    plt.get_figure().set_size_inches(6, 3.75)
    plt.get_figure().tight_layout()
    file_name = _get_plot_file_name(plot_name, plot_configuration.to_dict())
    plt.get_figure().savefig(os.path.join(path, file_name))
    plt.get_figure().clf()


def _run_benchmark(name: str, module: str, path: str, arguments: Mapping[str, Any]):
  """Run the experiment and dump the measurements.

  Arguments:
  name: A name used to dump the data.
  module: A Python module to run.
  path: A directory used to dump the data.
  arguments: A dictionary of command line arguments.
  """
  env = os.environ
  build_dir = env["IREE_LLVM_SANDBOX_BUILD_DIR"]
  env["PYTHONPATH"] = os.path.join(build_dir, "tools/sandbox/python_package")
  env["MLIR_RUNNER_UTILS_LIB"] = os.path.join(
      build_dir, "lib/libmlir_runner_utils.so")
  env["MLIR_C_RUNNER_UTILS_LIB"] = os.path.join(
      build_dir, "lib/libmlir_c_runner_utils.so")
  file_name = os.path.join(path, name + ".json")
  if os.path.exists(file_name):
    os.remove(file_name)
  args = ["python", "-m", module, "--dump_data", file_name]
  for argument, value in arguments.items():
    args.append(str.format(f"--{argument}"))
    if not isinstance(value, Sequence):
      value = [value]
    args.extend([str(v) for v in value])
  subprocess.run(args, shell=False, check=True)


def _parse_arguments() -> argparse.Namespace:
  """Plot argument parser.

  Arguments:
  base_path: Benchmark path prefix.
  peak_throughput: Peak throughput of the benchmark system.
  peak_bandwidth: Peak bandwidth of the benchmark system.
  """
  parser = argparse.ArgumentParser(description="run experiments")
  parser.add_argument("--base_path", "-p",
                      type=str,
                      nargs="?",
                      help="base path (e.g., -p benchmarks/)",
                      default="benchmarks/")
  parser.add_argument("--peak_throughput", "-t",
                      type=int,
                      nargs="?",
                      help="peak throughput (e.g., -t 192)",
                      default=192)
  parser.add_argument("--peak_bandwidth", "-b",
                      type=int,
                      nargs="?",
                      help="peak bandwidth (e.g., -b 100)",
                      default=100)
  parser.add_argument("--benchmark",
                      default=True,
                      action='store_true')
  parser.add_argument("--no-benchmark",
                      dest="benchmark",
                      action='store_false')
  parser.add_argument("--plotting",
                      default=True,
                      action='store_true')
  parser.add_argument("--no-plotting",
                      dest="plotting",
                      action='store_false')
  return parser.parse_args(sys.argv[1:])


def main():
  args = _parse_arguments()
  # Store the experimental data.
  if args.benchmark:
    for name, experiment in experiments.items():
      print(str.format(f"- running {name}"))
      path = os.path.join(args.base_path, name)
      _run_benchmark(name, experiment["module"], path, experiment["arguments"])
  # Plot the compute throughputs.
  if args.plotting:
    for name, experiment in experiments.items():
      print(str.format(f"- plotting {name}"))
      # Obtain the data.
      path = os.path.join(args.base_path, name)
      file_name = os.path.join(path, name + ".json")
      if not os.path.exists(file_name):
        print(str.format(f"  -> cannot find {file_name}"))
        continue
      data = pandas.read_json(file_name)
      # Plot the compute throughput.
      _plot_quantity("throughput", path, data, "gflop_per_s_per_iter",
                    "Compute Throughput [GFlop/s]",
                    args.peak_throughput,
                    str.format(f"Rpeak = {args.peak_throughput} GFlop/s"))
      # Plot the memory bandwidth.
      _plot_quantity("bandwidth", path, data, "gbyte_per_s_per_iter",
                    "Bandwidth [GB/s]",
                    args.peak_bandwidth,
                    str.format(f"Max Bandwidth = {args.peak_bandwidth} GB/s"))

if __name__ == '__main__':
  main()
