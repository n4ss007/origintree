from Bio import SeqIO
from Bio.Align import PairwiseAligner

filename = "data/sequences/Panthera_leo_COX1.fasta"

records = list(SeqIO.parse(filename, "fasta"))

aligner = PairwiseAligner()

print("Pairwise sequence identity:")
print()

for i in range(len(records)):
    for j in range(i + 1, len(records)):

        seq1 = str(records[i].seq)
        seq2 = str(records[j].seq)

        alignment = aligner.align(seq1, seq2)[0]

        aligned_seq1 = alignment[0]
        aligned_seq2 = alignment[1]

        matches = sum(
            a == b
            for a, b in zip(aligned_seq1, aligned_seq2)
        )

        identity = (
            matches / len(aligned_seq1)
        ) * 100

        print(
            f"{records[i].id} vs {records[j].id}: "
            f"{identity:.2f}%"
        )
