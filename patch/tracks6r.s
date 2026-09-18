| rung 10 — all six tracks, one per USB channel, read straight from the
| render blocks. No shadow, no phase offset.
|
| ch1..ch6 = tracks 1..6. The stereo mix is not sent over USB; mix from the
| stems in the DAW instead.
|
| This is rung 5's stub verbatim. Rungs 7 and 8 added a shadow copy and then a
| +12 read-index offset, both aimed at a "tearing" diagnosis that turned out to
| be wrong: the audible defect was the TX ring underrunning at depth 4, which
| re-sent its whole 24-frame contents once per audio tick. Measured as exact
| duplicates at lag 24 -- exactly the ring capacity -- in every depth-4 image
| and in none of the depth-9 ones. Rung 10 fixes the depth and reverts both
| experiments, which also frees the 768 B the shadow occupied so the ring can
| grow into it.
|
| Same hook as before (the feeder's copy loop at 0x40002a06) and NO geometry
| change: 6 channels, 24 B/frame, stride 192 are unchanged from rung 4.
|
| Register contract at the hook:
|     d0 = longword count = frames * 2 (source scaling is x8)
|     d1 = destination pointer
|     d3 = frame offset for this chunk
| The source pointer (sp@(36)) and d5 are unused -- we read the track blocks
| rather than the caller's stereo buffer.
|
| The mod-32 mask is load-bearing: a track block is 32 frames / 128 bytes, and
| d3 is not guaranteed to start at zero. Without the mask the loop reads past
| the end of track n into track n+1, which shows up as channel bleed. Rung 9
| removed it and was never flashed; do not revive that.

        .text
        .global tracks6_stub

        .equ TRACK_BASE,   0x80001b48
        .equ TRACK_STRIDE, 0x80
        .equ NTRACKS,      6
        .equ REJOIN,       0x40002a26

tracks6_stub:
        lea     %sp@(-44),%sp
        movem.l %d0-%d7/%a0-%a2,%sp@

        movea.l %d1,%a1                 | destination
        moveq   #31,%d4                 | block mask
        move.l  %d3,%d6
        and.l   %d4,%d6                 | frame index within the 32-frame block
        lsr.l   #1,%d0                  | longwords -> frames
        ble     .Ldone

.Lframe:
        movea.l #TRACK_BASE,%a2
        lea     %a2@(0,%d6:l:4),%a2     | &track0[frame]
        moveq   #NTRACKS,%d7

.Ltrack:
        move.l  %a2@,%d2
        .short  0x02c2                  | byterev %d2
        move.l  %d2,%a1@+
        lea     %a2@(TRACK_STRIDE),%a2  | next track's block
        subq.l  #1,%d7
        bne     .Ltrack

        addq.l  #1,%d6
        and.l   %d4,%d6
        subq.l  #1,%d0
        bgt     .Lframe

.Ldone:
        movem.l %sp@,%d0-%d7/%a0-%a2
        lea     %sp@(44),%sp
        jmp     REJOIN
