// Lazily allocated source-group concentration blocks. GPL-3.0, same license as GRAL.
using System;
using System.Collections.Generic;
using System.Runtime.CompilerServices;

namespace GRAL_2001
{
    // Writers must hold the cell lock, as with the former float[]/double[] cells.
    // Reads, output, clearing and checkpoint I/O keep the existing phase barriers.
    public readonly struct SourceGroupBuffer<T> where T : unmanaged
    {
        // One reference per cell, as in the original jagged arrays.
        // Legacy cells keep the original T[] allocation without an extra wrapper object.
        private readonly object storage;
        public object SyncRoot => storage;
        public int Length => storage is T[] values ? values.Length : ((SparseCell)storage).Length;

        public SourceGroupBuffer(int length)
        {
            if (length < 1) throw new ArgumentOutOfRangeException(nameof(length));
            storage = length <= 100 ? new T[length] : new SparseCell(length);
        }

        public T this[int index]
        {
            [MethodImpl(MethodImplOptions.AggressiveInlining)]
            get => storage is T[] values ? values[index] : ((SparseCell)storage)[index];
            [MethodImpl(MethodImplOptions.AggressiveInlining)]
            set
            {
                if (storage is T[] values) values[index] = value;
                else ((SparseCell)storage)[index] = value;
            }
        }

        public void Clear()
        {
            if (storage is T[] values) Array.Clear(values);
            else ((SparseCell)storage).Clear();
        }

        private sealed class SparseCell
        {
            private const int BlockShift = 5;
            private const int BlockSize = 1 << BlockShift;
            private T[] dense;
            private T[][] blocks;
            private int allocatedBlocks;
            public int Length { get; }

            public SparseCell(int length) { Length = length; }

            public T this[int index]
            {
                [MethodImpl(MethodImplOptions.AggressiveInlining)]
                get
                {
                    if ((uint)index >= (uint)Length) throw new IndexOutOfRangeException();
                    if (dense != null) return dense[index];
                    T[] block = blocks == null ? null : blocks[index >> BlockShift];
                    return block == null ? default : block[index & (BlockSize - 1)];
                }
                [MethodImpl(MethodImplOptions.AggressiveInlining)]
                set
                {
                    if ((uint)index >= (uint)Length) throw new IndexOutOfRangeException();
                    if (dense != null) { dense[index] = value; return; }
                    int slot = index >> BlockShift;
                    T[] block = blocks == null ? null : blocks[slot];
                    if (block == null)
                    {
                        if (EqualityComparer<T>.Default.Equals(value, default)) return;
                        if (blocks == null) blocks = new T[(Length + BlockSize - 1) >> BlockShift][];
                        block = new T[Math.Min(BlockSize, Length - slot * BlockSize)];
                        blocks[slot] = block;
                        allocatedBlocks++;
                    }
                    block[index & (BlockSize - 1)] = value;
                    if (allocatedBlocks * BlockSize >= Length * 3 / 4) MakeDense();
                }
            }

            private void MakeDense()
            {
                var values = new T[Length];
                for (int i = 0; i < blocks.Length; i++)
                    if (blocks[i] != null) Array.Copy(blocks[i], 0, values, i * BlockSize, blocks[i].Length);
                dense = values;
                blocks = null;
            }

            public void Clear() { dense = null; blocks = null; allocatedBlocks = 0; }
        }
    }
}
