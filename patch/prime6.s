| rung 4 helper — the 6-channel priming block.
|
| Replaces 0x400027e8..0x400027fd (22 bytes) in FUN_40002778. The work needs
| 24 bytes and only 22 exist, and squeezing it is how the length-field store
| got silently dropped once already -- so the whole block moves out here where
| there is no budget pressure, and jumps back.
|
| On entry a2 = the dTD being primed. Sets:
|   a2@(4)  = dTD token: 144 bytes, active
|   a2@(0)  = 0xdead0001 terminator
|   a2@(32) = 144, the driver's own length field, which 0x40003f10 reads to
|             compute bytes-transferred (length - remaining). Getting this
|             wrong is not cosmetic.
| 144 = 6 frames x 6 channels x 4 bytes.

        .text
        .global prime6_helper
        .equ RETURN, 0x400027fe

prime6_helper:
        move.l  #0x00900080,%d0         | 144 bytes << 16 | active
        move.l  %d0,%a2@(4)
        move.l  #0xdead0001,%a2@
        moveq   #18,%d1
        lsl.l   #3,%d1                  | 18*8 = 144 (moveq cannot encode 144)
        move.l  %d1,%a2@(32)
        jmp     RETURN
