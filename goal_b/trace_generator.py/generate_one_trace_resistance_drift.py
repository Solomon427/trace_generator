import os
import random
import numpy as np
import csv

# --- Configuration ---
NUM_ROWS = 100000
BLOCK_SIZE_BITS = 512
NUM_BLOCKS = 64

ZERO_PROB = 0.88
IDLE_PROB = 0.01
REUSE_PROB = 0.1
MLC_BITS = 2
PRETTY_PRINT_MLC = False

READ_LATENCY_NS = 50
WRITE_LATENCY_NS = 500

DRIFT_EXPONENT = 0.1
DRIFT_SENSITIVITY = 0.01

N_FILES = 1  # Number of trace sets to generate
OUTPUT_DIR = r'D:'
#TRACE_FILENAME_CLEAN = "solomon_trace_clean_1.nvt"
#TRACE_FILENAME_DRIFT = "solomon_trace_drift_1.nvt"
#TRACE_FILENAME_LABELS = "solomon_trace_labels_1.csv"

# --- State Tracking ---
memory_state = {}
last_write_time = {}
used_addresses = set()
read_counts = {}

def generate_biased_binary(length, p_zero):
    bits = np.random.rand(length) < p_zero
    binary_string = ''.join('0' if bit else '1' for bit in bits)
    if MLC_BITS > 1 and PRETTY_PRINT_MLC:
        grouped = ' '.join(binary_string[i:i+MLC_BITS] for i in range(0, len(binary_string), MLC_BITS))
        return grouped
    return binary_string

def generate_address(reuse_prob):
    if used_addresses and random.random() < reuse_prob:
        return random.choice(list(used_addresses))
    else:
        addr = random.randint(0, NUM_BLOCKS - 1) * BLOCK_SIZE_BITS
        used_addresses.add(addr)
        return addr

def apply_resistance_drift(data, time_since_write_ns):
    if PRETTY_PRINT_MLC:
        data = data.replace(' ', '')

    drifted = []
    for i in range(0, len(data), MLC_BITS):
        unit = data[i:i+MLC_BITS]
        drift_factor = (time_since_write_ns / 1e9) ** DRIFT_EXPONENT
        drift_prob = drift_factor * DRIFT_SENSITIVITY
        if random.random() < drift_prob:
            flipped = ''.join('1' if b == '0' else '0' for b in unit)
            drifted.append(flipped)
        else:
            drifted.append(unit)

    result = ''.join(drifted)
    if MLC_BITS > 1 and PRETTY_PRINT_MLC:
        result = ' '.join(result[i:i+MLC_BITS] for i in range(0, len(result), MLC_BITS))
    return result

def generate_realistic_trace(clean_path, drifted_path, labels_path, num_rows, zero_prob, idle_prob):
    current_time = 0

    with open(clean_path, 'w') as clean_f, \
         open(drifted_path, 'w') as drift_f, \
         open(labels_path, 'w', newline='') as label_f:

        label_writer = csv.writer(label_f)
        label_writer.writerow(["cycle", "label", "time_since_last_write", "op", "read_count_on_block", "drift_pct"])

        for i in range(num_rows):
            op = random.choice(['R', 'W'])
            addr = generate_address(REUSE_PROB)
            read_counts.setdefault(addr, 0)

            if op == 'R':
                data = memory_state.get(addr, generate_biased_binary(BLOCK_SIZE_BITS, zero_prob))
                latency = READ_LATENCY_NS

                if addr in last_write_time:
                    time_since_write = current_time - last_write_time[addr]
                    drifted_data = apply_resistance_drift(data, time_since_write)
                    bit_errors = sum(b1 != b2 for b1, b2 in zip(data, drifted_data))
                    drift_pct = bit_errors / len(data)
                    label = int(bit_errors > 0)
                else:
                    time_since_write = -1
                    drifted_data = data  # no drift
                    drift_pct = 0.0
                    label = 0

                read_counts[addr] += 1

            else:  # Write
                data = generate_biased_binary(BLOCK_SIZE_BITS, zero_prob)
                memory_state[addr] = data
                last_write_time[addr] = current_time
                latency = WRITE_LATENCY_NS
                drifted_data = data
                time_since_write = 0
                drift_pct = 0.0
                label = 0

            if random.random() < idle_prob:
                current_time += random.randint(100, 10000)
            current_time += latency

            cycle = i + 1
            clean_f.write(f"{cycle} {op} {hex(addr)} {data} {current_time}\n")
            drift_f.write(f"{cycle} {op} {hex(addr)} {drifted_data} {current_time}\n")
            label_writer.writerow([
                cycle,
                label,
                time_since_write,
                1 if op == 'R' else 0,
                read_counts[addr],
                drift_pct
            ])


# --- Create and Run ---
os.makedirs(OUTPUT_DIR, exist_ok=True)

for i in range(N_FILES):
    clean_path = os.path.join(OUTPUT_DIR, f"solomon_trace_clean_{i}.nvt")
    drift_path = os.path.join(OUTPUT_DIR, f"solomon_trace_drift_{i}.nvt")
    labels_path = os.path.join(OUTPUT_DIR, f"solomon_trace_labels_{i}.csv")

    memory_state.clear()
    last_write_time.clear()
    used_addresses.clear()
    read_counts.clear()

    print(f"Generating trace file set {i + 1}/{N_FILES}")
    generate_realistic_trace(clean_path, drift_path, labels_path, NUM_ROWS, ZERO_PROB, IDLE_PROB)

print("I finished running!")