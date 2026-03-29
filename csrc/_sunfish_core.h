#ifndef _SUNFISH_CORE_H
#define _SUNFISH_CORE_H

/* Board constants (10x12 mailbox) */
#define BOARD_SIZE 120
#define DIR_N  (-10)
#define DIR_E  1
#define DIR_S  10
#define DIR_W  (-1)
#define A1 91
#define H1 98
#define A8 21
#define H8 28

/* Maximum moves in any position (generous upper bound) */
#define MAX_MOVES 256

/* Direction arrays per piece type */
static const int PAWN_DIRS[] = { -10, -20, -11, -9 };
static const int PAWN_NDIRS = 4;

/* N+N+E, E+N+E, E+S+E, S+S+E, S+S+W, W+S+W, W+N+W, N+N+W */
static const int KNIGHT_DIRS[] = { -19, -8, 12, 21, 19, 8, -12, -21 };
static const int KNIGHT_NDIRS = 8;

/* N+E, S+E, S+W, N+W */
static const int BISHOP_DIRS[] = { -9, 11, 9, -11 };
static const int BISHOP_NDIRS = 4;

/* N, E, S, W */
static const int ROOK_DIRS[] = { -10, 1, 10, -1 };
static const int ROOK_NDIRS = 4;

/* N, E, S, W, N+E, S+E, S+W, N+W */
static const int QUEEN_KING_DIRS[] = { -10, 1, 10, -1, -9, 11, 9, -11 };
static const int QUEEN_KING_NDIRS = 8;

static const int NO_DIRS[] = { 0 };
static const int NO_NDIRS = 0;

/* 128-byte lookup tables for O(1) character classification */

static const unsigned char IS_UPPER[128] = {
    ['A'] = 1, ['B'] = 1, ['C'] = 1, ['D'] = 1, ['E'] = 1, ['F'] = 1,
    ['G'] = 1, ['H'] = 1, ['I'] = 1, ['J'] = 1, ['K'] = 1, ['L'] = 1,
    ['M'] = 1, ['N'] = 1, ['O'] = 1, ['P'] = 1, ['Q'] = 1, ['R'] = 1,
    ['S'] = 1, ['T'] = 1, ['U'] = 1, ['V'] = 1, ['W'] = 1, ['X'] = 1,
    ['Y'] = 1, ['Z'] = 1,
};

static const unsigned char IS_LOWER[128] = {
    ['a'] = 1, ['b'] = 1, ['c'] = 1, ['d'] = 1, ['e'] = 1, ['f'] = 1,
    ['g'] = 1, ['h'] = 1, ['i'] = 1, ['j'] = 1, ['k'] = 1, ['l'] = 1,
    ['m'] = 1, ['n'] = 1, ['o'] = 1, ['p'] = 1, ['q'] = 1, ['r'] = 1,
    ['s'] = 1, ['t'] = 1, ['u'] = 1, ['v'] = 1, ['w'] = 1, ['x'] = 1,
    ['y'] = 1, ['z'] = 1,
};

static const unsigned char IS_SPACE[128] = {
    [' '] = 1, ['\n'] = 1, ['\t'] = 1, ['\r'] = 1,
};

/* Piece identity lookup tables */
static const unsigned char IS_POWERED[128] = {
    ['A'] = 1, ['C'] = 1, ['D'] = 1, ['T'] = 1, ['X'] = 1, ['Y'] = 1,
};

static const unsigned char IS_PAWN[128] = {
    ['P'] = 1, ['A'] = 1,
};

static const unsigned char IS_KING[128] = {
    ['K'] = 1, ['Y'] = 1,
};

static const unsigned char IS_ROCK[128] = {
    ['O'] = 1, ['o'] = 1,
};

static const unsigned char IS_NON_SLIDER[128] = {
    ['P'] = 1, ['N'] = 1, ['K'] = 1, ['A'] = 1, ['C'] = 1, ['Y'] = 1,
};

/* Get directions and count for a piece character.
 * Returns pointers to static arrays. */
static inline void get_directions(char p, const int **dirs, int *ndirs) {
    switch (p) {
        case 'P': case 'A':
            *dirs = PAWN_DIRS; *ndirs = PAWN_NDIRS; break;
        case 'N': case 'C':
            *dirs = KNIGHT_DIRS; *ndirs = KNIGHT_NDIRS; break;
        case 'B': case 'D':
            *dirs = BISHOP_DIRS; *ndirs = BISHOP_NDIRS; break;
        case 'R': case 'T':
            *dirs = ROOK_DIRS; *ndirs = ROOK_NDIRS; break;
        case 'Q': case 'X':
        case 'K': case 'Y':
            *dirs = QUEEN_KING_DIRS; *ndirs = QUEEN_KING_NDIRS; break;
        default:
            *dirs = NO_DIRS; *ndirs = NO_NDIRS; break;
    }
}

/* Promotion piece arrays (must match Python PROMOTION_PIECES order) */
static const char PROM_P[] = { 'N', 'B', 'R', 'Q' };
static const char PROM_A[] = { 'C', 'D', 'T', 'X' };
static const int PROM_COUNT = 4;

#endif /* _SUNFISH_CORE_H */
