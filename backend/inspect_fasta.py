from Bio import SeqIO

filename = "data/sequences/Panthera_leo_COX1.fasta"

records = list(SeqIO.parse(filename, "fasta"))

print("Number of sequences:", len(records))

for record in records:
    sequence = str(record.seq)

    print(
        f"{record.id}: "
        f"length={len(sequence)}, "
        f"ambiguous_bases={sequence.upper().count('N')}"
    )
