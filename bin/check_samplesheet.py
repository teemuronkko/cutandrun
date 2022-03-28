#!/usr/bin/env python

# This script is based on the example at: https://raw.githubusercontent.com/nf-core/test-datasets/atacseq/design.csv


import os
import sys
import errno
import argparse


def parse_args(args=None):
    Description = "Reformat nf-core/cutandrun samplesheet file and check its contents."
    Epilog = "Example usage: python check_samplesheet.py <FILE_IN> <FILE_OUT>"

    parser = argparse.ArgumentParser(description=Description, epilog=Epilog)
    parser.add_argument("FILE_IN", help="Input samplesheet file.")
    parser.add_argument("FILE_OUT", help="Output file.")
    parser.add_argument("IGG", help="Boolean for whether or not igg is given")
    return parser.parse_args(args)


def make_dir(path):
    if len(path) > 0:
        try:
            os.makedirs(path)
        except OSError as exception:
            if exception.errno != errno.EEXIST:
                raise exception


def print_error(error, context="Line", context_str=""):
    error_str = "ERROR: Please check samplesheet -> {}".format(error)
    if context != "" and context_str != "":
        error_str = "ERROR: Please check samplesheet -> {}\n{}: '{}'".format(
            error, context.strip(), context_str.strip()
        )
    print(error_str)
    sys.exit(1)


def check_samplesheet(file_in, file_out, igg_control):
    """
    This function checks that the samplesheet follows the following structure:

    group,replicate,fastq_1,fastq_2,control
    WT,1,WT_LIB1_REP1_1.fastq.gz,WT_LIB1_REP1_2.fastq.gz,IGG_group1
    WT,1,WT_LIB2_REP1_1.fastq.gz,WT_LIB2_REP1_2.fastq.gz,IGG_group1
    WT,2,WT_LIB1_REP2_1.fastq.gz,WT_LIB1_REP2_2.fastq.gz,IGG_group1
    KO,1,KO_LIB1_REP1_1.fastq.gz,KO_LIB1_REP1_2.fastq.gz,IGG_group1
    IGG_group1,1,KO_LIB1_REP1_1.fastq.gz,IGG_LIB1_REP1_2.fastq.gz, 
    IGG_group1,2,KO_LIB1_REP1_1.fastq.gz,IGG_LIB1_REP1_2.fastq.gz, 
    """

    igg_present = False

    num_fastq_list     = []
    sample_names_list  = []
    control_names_list = []
    is_control         = []
    sample_run_dict = {}
    with open(file_in, "r") as fin:

        ## Check header
        MIN_COLS = 3
        HEADER = ["group", "replicate", "fastq_1", "fastq_2", "control"]
        header = [x.strip('"') for x in fin.readline().strip().split(",")]
        if header[: len(HEADER)] != HEADER:
            print("ERROR: Please check samplesheet header -> {} != {}".format(",".join(header), ",".join(HEADER)))
            sys.exit(1)

        ## Check sample entries
        for line in fin:
            lspl = [x.strip().strip('"') for x in line.strip().split(",")]

            ## Set control_present to true if the control column is not empty
            if not igg_present:
                if lspl[4] != "":
                    igg_present = True 

            ## Check valid number of columns per row
            if len(lspl) != 5:
                print_error(
                    "Invalid number of columns (should be {})!".format(len(HEADER)),
                    "Line",
                    line,
                )

            ## Check valid number of populated columns per row
            num_cols = len([x for x in lspl if x])
            if num_cols < MIN_COLS:
                print_error(
                    "Invalid number of populated columns (minimum = {})!".format(MIN_COLS),
                    "Line",
                    line,
                )

            ## Check sample name entries
            sample, replicate, fastq_1, fastq_2, control = lspl[: len(HEADER)]
            if sample:
                if sample.find(" ") != -1:
                    print_error("Group entry contains spaces!", "Line", line)
            else:
                print_error("Group entry has not been specified!", "Line", line)

            if control:
                if control.find(" ") != -1:
                    print_error("Control entry contains spaces!", "Line", line)

            ## Check control sample name is not equal to sample name entry
            if sample == control:
                print_error("Control entry and sample entry must be different!", "Line", line)

            ## Check replicate entry is integer
            if not replicate.isdigit():
                print_error("Replicate id not an integer!", "Line", line)
            replicate = int(replicate)

            ## Create control identity
            if control != "":
                    is_control = "0"
            else:
                is_control = "1"

            ## Check FastQ file extension
            for fastq in [fastq_1, fastq_2]:
                if fastq:
                    if fastq.find(" ") != -1:
                        print_error("FastQ file contains spaces!", "Line", line)
                    if not fastq.endswith(".fastq.gz") and not fastq.endswith(".fq.gz"):
                        print_error(
                            "FastQ file does not have extension '.fastq.gz' or '.fq.gz'!",
                            "Line",
                            line,
                        )
            num_fastq = len([fastq for fastq in [fastq_1, fastq_2] if fastq])
            num_fastq_list.append(num_fastq)

            ## Auto-detect paired-end/single-end
            sample_info = []
            if sample and fastq_1 and fastq_2:  ## Paired-end short reads
                sample_info = [sample, str(replicate), control, "0", fastq_1, fastq_2, is_control]
            elif sample and fastq_1 and not fastq_2:  ## Single-end short reads
                sample_info = [sample, str(replicate), control, "1", fastq_1, fastq_2, is_control]
            else:
                print_error("Invalid combination of columns provided!", "Line", line)
            ## Create sample mapping dictionary = {sample: {replicate : [ single_end, fastq_1, fastq_2 ]}}
            if sample not in sample_run_dict:
                sample_run_dict[sample] = {}
            if replicate not in sample_run_dict[sample]:
                sample_run_dict[sample][replicate] = [sample_info]
            else:
                if sample_info in sample_run_dict[sample][replicate]:
                    print_error("Samplesheet contains duplicate rows!", "Line", line)
                else:
                    sample_run_dict[sample][replicate].append(sample_info)

            ## Store unique group names
            if sample not in sample_names_list:
                sample_names_list.append(sample)

            ## Store unique control names
            if control not in control_names_list:
                control_names_list.append(control)

    ## Check data is either paired-end/single-end and not both
    if min(num_fastq_list) != max(num_fastq_list):
        print_error("Mixture of paired-end and single-end reads!")
        sys.exit(1)

    ## Check control group exists
    for ctrl in control_names_list:
        if ctrl != "" and ctrl not in sample_names_list:
            CTRL = ctrl
            print_error("Each control entry must match at least one group entry! Unmatched control entry: {}.".format(CTRL))
            sys.exit(1)

    ## Check igg_control parameter is consistent with input groups
    if (igg_control == 'true' and not igg_present):
        print("ERROR: No 'igg' group was found in " + str(file_in) + " If you are not supplying an IgG control, please specify --igg_control 'false' on command line.")
        sys.exit(1)

    if (igg_control == 'false' and igg_present):
        print("ERROR: Parameter --igg_control was set to false, but an 'igg' group was found in " + str(file_in) + ".")
        sys.exit(1)

    ## Write validated samplesheet with appropriate columns
    if len(sample_run_dict) > 0:
        out_dir = os.path.dirname(file_out)
        make_dir(out_dir)
        with open(file_out, "w") as fout:

            fout.write(",".join(["id", "group", "replicate", "control", "single_end", "fastq_1", "fastq_2", "is_control"]) + "\n")
            for sample in sorted(sample_run_dict.keys()):

                ## Check that replicate ids are in format 1..<NUM_REPS>
                uniq_rep_ids = set(sample_run_dict[sample].keys())
                if len(uniq_rep_ids) != max(uniq_rep_ids):
                    print_error(
                        "Replicate ids must start with 1..<num_replicates>!",
                        "Group",
                        sample,
                    )
                for replicate in sorted(sample_run_dict[sample].keys()):

                    ## Check tech reps have same control group id
                    check_group = sample_run_dict[sample][replicate][0][2]
                    for tech_rep in sample_run_dict[sample][replicate]:
                        if tech_rep[2] != check_group:
                            print_error(
                                "Control group must match within technical replicates",
                                tech_rep[2]
                            )

                    ## Check that multiple runs of the same sample are of the same datatype
                    if not all(
                        x[0] == sample_run_dict[sample][replicate][0][0] for x in sample_run_dict[sample][replicate]
                    ):
                        print_error(
                            "Multiple runs of a sample must be of the same datatype!",
                            "Group",
                            sample,
                        )
                    ## Write to file
                    for idx, sample_info in enumerate(sample_run_dict[sample][replicate]):
                        sample_id = "{}_R{}_T{}".format(sample, replicate, idx + 1)
                        fout.write(",".join([sample_id] + sample_info) + "\n")


def main(args=None):
    args = parse_args(args)
    check_samplesheet(args.FILE_IN, args.FILE_OUT, args.IGG)


if __name__ == "__main__":
    sys.exit(main())
