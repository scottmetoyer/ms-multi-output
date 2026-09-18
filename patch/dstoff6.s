| rung 4 fix — destination frame offset for six channels.
|
| Replaces 0x400029e4..0x400029ed (10 bytes), which computed
|     d1 = slot_base + frames_in_slot * 16
| i.e. the FOUR-channel frame size. Six channels are 24 bytes per frame, and
| 24 is not a power of two, so it needs (x<<4)+(x<<3) -- which does not fit the
| 2-byte shift site. Hence a helper.
|
| This site was simply missed when rung 4 was built: the stride, the source
| offset and the token were all rescaled, but the destination frame offset was
| left at the 4-channel value. The result is the destination advancing 16 bytes
| per frame while the stub writes 24, so chunks overlap and the host slices the
| stream wrongly -- which presents as all channels looking like copies.
|
| On entry: d0 = frames already in the current slot.
| On exit:  d1 = destination pointer. d0 is dead (0x400029ee reloads it from d4).

        .text
        .global dstoff6_helper
        .equ SLOT_BASE, 0x404af45c
        .equ RETURN,    0x400029ee

dstoff6_helper:
        move.l  %d0,%d1
        lsl.l   #4,%d0                  | frames * 16
        lsl.l   #3,%d1                  | frames * 8
        add.l   %d1,%d0                 | frames * 24
        move.l  SLOT_BASE,%d1           | current slot base
        add.l   %d0,%d1                 | d1 = slot_base + frames*24
        jmp     RETURN
