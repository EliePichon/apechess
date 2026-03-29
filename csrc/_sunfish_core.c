#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdlib.h>
#include "_sunfish_core.h"
#include "tables.h"

/* Pre-created Python string objects for promotion chars and empty string */
static PyObject *g_empty_str = NULL;
static PyObject *g_prom_strs[128]; /* indexed by char: 'N','B','R','Q','C','D','T','X' */

/* Internal move struct for stack-allocated buffer */
typedef struct {
    int i;
    int j;
    char prom; /* '\0' for no promotion */
} CMove;

/* Scored move for sorting (idx preserves original order for stable sort) */
typedef struct {
    int score;
    int idx;
    CMove move;
} ScoredMove;

/*
 * gen_moves_internal: C implementation of Position.gen_moves()
 *
 * Fills the moves[] buffer with all pseudo-legal moves.
 * Returns the number of moves generated.
 *
 * This must produce moves in IDENTICAL order to the Python gen_moves()
 * to preserve node count invariance.
 */
static int gen_moves_internal(
    const char *board,
    int wc0, int wc1,  /* white castling rights (queen-side, king-side) */
    int bc0, int bc1,  /* black castling rights */
    int ep,            /* en passant square (0 if none) */
    int kp,            /* king passant square (0 if none) */
    CMove *moves,
    int max_moves
) {
    int count = 0;
    int i, di, j;
    char p, q;
    const int *dirs;
    int ndirs;

    for (i = 0; i < BOARD_SIZE; i++) {
        p = board[i];
        /* Skip non-uppercase and rocks (rocks don't move) */
        if (!IS_UPPER[(unsigned char)p] || p == 'O')
            continue;

        get_directions(p, &dirs, &ndirs);

        for (di = 0; di < ndirs; di++) {
            int d = dirs[di];
            for (j = i + d; ; j += d) {
                q = board[j];

                /* Stay inside the board */
                if (IS_SPACE[(unsigned char)q])
                    break;

                /* Off friendly pieces (excluding rocks for powered pieces) */
                if (IS_UPPER[(unsigned char)q]) {
                    if (q == 'O' && IS_POWERED[(unsigned char)p]) {
                        /* powered piece can land on rock — fall through */
                    } else {
                        break;
                    }
                }

                /* Lowercase rocks block normal pieces but not powered ones */
                if (q == 'o' && !IS_POWERED[(unsigned char)p])
                    break;

                /* Pawn move, double move and capture */
                if (IS_PAWN[(unsigned char)p]) {
                    /* Forward moves blocked by non-empty square
                     * (exception: powered pawn A can land on rocks) */
                    if ((d == DIR_N || d == DIR_N + DIR_N) &&
                        q != '.' &&
                        !(IS_ROCK[(unsigned char)q] && p == 'A')) {
                        break;
                    }
                    /* Double move only from starting rank, and middle square must be empty */
                    if (d == DIR_N + DIR_N &&
                        (i < A1 + DIR_N || board[i + DIR_N] != '.')) {
                        break;
                    }
                    /* Diagonal capture requires target or en passant / king passant */
                    if ((d == DIR_N + DIR_W || d == DIR_N + DIR_E) &&
                        q == '.' &&
                        j != ep &&
                        j != kp && j != kp - 1 && j != kp + 1) {
                        break;
                    }
                    /* Promotion: if we reach the last rank */
                    if (j >= A8 && j <= H8) {
                        const char *proms = (p == 'A') ? PROM_A : PROM_P;
                        int pi;
                        for (pi = 0; pi < PROM_COUNT && count < max_moves; pi++) {
                            moves[count].i = i;
                            moves[count].j = j;
                            moves[count].prom = proms[pi];
                            count++;
                        }
                        break;
                    }
                }

                /* Yield the move */
                if (count < max_moves) {
                    moves[count].i = i;
                    moves[count].j = j;
                    moves[count].prom = '\0';
                    count++;
                }

                /* Stop crawlers from sliding, and stop after captures
                 * (including landing on rocks) */
                if (IS_NON_SLIDER[(unsigned char)p] ||
                    IS_LOWER[(unsigned char)q] ||
                    IS_ROCK[(unsigned char)q]) {
                    break;
                }

                /* Castling: rook sliding next to king */
                if (i == A1 && IS_KING[(unsigned char)board[j + DIR_E]] && wc0) {
                    if (count < max_moves) {
                        moves[count].i = j + DIR_E;
                        moves[count].j = j + DIR_W;
                        moves[count].prom = '\0';
                        count++;
                    }
                }
                if (i == H1 && IS_KING[(unsigned char)board[j + DIR_W]] && wc1) {
                    if (count < max_moves) {
                        moves[count].i = j + DIR_W;
                        moves[count].j = j + DIR_E;
                        moves[count].prom = '\0';
                        count++;
                    }
                }
            }
        }
    }

    return count;
}

/*
 * value_internal: C implementation of Position.value()
 *
 * Computes the positional score delta for a move.
 * Must produce identical results to the Python value() method.
 */
static int value_internal(
    const char *board,
    int ep,
    int kp,
    int mi, int mj, char prom
) {
    char p = board[mi];
    char q = board[mj];
    int pi = PIECE_INDEX[(unsigned char)p];

    /* Base PST delta */
    int score = PST[pi][mj] - PST[pi][mi];

    /* Capture (exclude rocks which are not capturable) */
    if (IS_LOWER[(unsigned char)q] && q != 'o') {
        int qi = PIECE_INDEX_LOWER[(unsigned char)q];
        score += PST[qi][119 - mj];
    }

    /* Castling check detection */
    if (kp != 0) {
        int diff = mj - kp;
        if (diff < 0) diff = -diff;
        if (diff < 2) {
            score += PST[5][119 - mj]; /* PST index 5 = King */
        }
    }

    /* Castling rook movement */
    if (IS_KING[(unsigned char)p]) {
        int diff = mi - mj;
        if (diff < 0) diff = -diff;
        if (diff == 2) {
            score += PST[3][(mi + mj) / 2]; /* PST index 3 = Rook */
            score -= PST[3][mj < mi ? A1 : H1];
        }
    }

    /* Special pawn stuff */
    if (IS_PAWN[(unsigned char)p]) {
        if (mj >= A8 && mj <= H8) {
            int prom_idx = PIECE_INDEX[(unsigned char)prom];
            score += PST[prom_idx][mj] - PST[pi][mj];
        }
        if (mj == ep) {
            score += PST[pi][119 - (mj + DIR_S)];
        }
    }

    return score;
}

/*
 * Comparator for qsort: descending by (score, i, j, prom).
 * Python sorts (score, (i, j, prom)) tuples with reverse=True,
 * so on score ties it compares (i, j, prom) in descending order.
 */
static int scored_move_cmp(const void *a, const void *b) {
    const ScoredMove *sa = (const ScoredMove *)a;
    const ScoredMove *sb = (const ScoredMove *)b;
    /* Descending by score */
    if (sa->score != sb->score)
        return (sb->score > sa->score) ? 1 : -1;
    /* Descending by i */
    if (sa->move.i != sb->move.i)
        return (sb->move.i > sa->move.i) ? 1 : -1;
    /* Descending by j */
    if (sa->move.j != sb->move.j)
        return (sb->move.j > sa->move.j) ? 1 : -1;
    /* Descending by prom (compare char values) */
    if (sa->move.prom != sb->move.prom)
        return (sb->move.prom > sa->move.prom) ? 1 : -1;
    return 0;
}

/*
 * Convert internal move buffer to Python list of (i, j, prom) tuples.
 */
static PyObject *moves_to_pylist(CMove *moves, int count) {
    PyObject *list = PyList_New(count);
    if (!list) return NULL;

    int k;
    for (k = 0; k < count; k++) {
        PyObject *prom;
        if (moves[k].prom == '\0') {
            prom = g_empty_str;
            Py_INCREF(prom);
        } else {
            prom = g_prom_strs[(unsigned char)moves[k].prom];
            if (!prom) {
                /* Shouldn't happen, but safety fallback */
                char buf[2] = { moves[k].prom, '\0' };
                prom = PyUnicode_FromString(buf);
                if (!prom) {
                    Py_DECREF(list);
                    return NULL;
                }
            } else {
                Py_INCREF(prom);
            }
        }

        PyObject *tuple = PyTuple_New(3);
        if (!tuple) {
            Py_DECREF(prom);
            Py_DECREF(list);
            return NULL;
        }

        PyTuple_SET_ITEM(tuple, 0, PyLong_FromLong(moves[k].i));
        PyTuple_SET_ITEM(tuple, 1, PyLong_FromLong(moves[k].j));
        PyTuple_SET_ITEM(tuple, 2, prom); /* steals reference */

        PyList_SET_ITEM(list, k, tuple); /* steals reference */
    }

    return list;
}

/*
 * Python-callable gen_moves(board, wc, bc, ep, kp) -> list[(i, j, prom)]
 */
static PyObject *py_gen_moves(PyObject *self, PyObject *args) {
    const char *board;
    Py_ssize_t board_len;
    PyObject *wc_tuple, *bc_tuple;
    int ep, kp;

    if (!PyArg_ParseTuple(args, "s#OOii",
                          &board, &board_len,
                          &wc_tuple, &bc_tuple,
                          &ep, &kp)) {
        return NULL;
    }

    if (board_len != BOARD_SIZE) {
        PyErr_Format(PyExc_ValueError,
                     "Board must be %d characters, got %zd",
                     BOARD_SIZE, board_len);
        return NULL;
    }

    /* Extract castling booleans from tuples */
    int wc0 = PyObject_IsTrue(PyTuple_GetItem(wc_tuple, 0));
    int wc1 = PyObject_IsTrue(PyTuple_GetItem(wc_tuple, 1));
    int bc0 = PyObject_IsTrue(PyTuple_GetItem(bc_tuple, 0));
    int bc1 = PyObject_IsTrue(PyTuple_GetItem(bc_tuple, 1));

    if (PyErr_Occurred()) return NULL;

    CMove moves[MAX_MOVES];
    int count = gen_moves_internal(board, wc0, wc1, bc0, bc1, ep, kp,
                                   moves, MAX_MOVES);

    return moves_to_pylist(moves, count);
}

/*
 * Python-callable value(board, ep, kp, i, j, prom) -> int
 */
static PyObject *py_value(PyObject *self, PyObject *args) {
    const char *board;
    Py_ssize_t board_len;
    int ep, kp, mi, mj;
    const char *prom_str;
    Py_ssize_t prom_len;

    if (!PyArg_ParseTuple(args, "s#iiiis#",
                          &board, &board_len,
                          &ep, &kp,
                          &mi, &mj,
                          &prom_str, &prom_len)) {
        return NULL;
    }

    if (board_len != BOARD_SIZE) {
        PyErr_Format(PyExc_ValueError,
                     "Board must be %d characters, got %zd",
                     BOARD_SIZE, board_len);
        return NULL;
    }

    char prom = (prom_len > 0) ? prom_str[0] : '\0';
    int score = value_internal(board, ep, kp, mi, mj, prom);

    return PyLong_FromLong(score);
}

/*
 * Python-callable score_and_sort_moves(board, wc, bc, ep, kp)
 *   -> list[(score, (i, j, prom))] sorted descending by score
 *
 * This is the BIG WIN: gen_moves + value + sort in one C call.
 * Eliminates Python generator overhead, per-move round-trips, and Python sort.
 */
static PyObject *py_score_and_sort_moves(PyObject *self, PyObject *args) {
    const char *board;
    Py_ssize_t board_len;
    PyObject *wc_tuple, *bc_tuple;
    int ep, kp;

    if (!PyArg_ParseTuple(args, "s#OOii",
                          &board, &board_len,
                          &wc_tuple, &bc_tuple,
                          &ep, &kp)) {
        return NULL;
    }

    if (board_len != BOARD_SIZE) {
        PyErr_Format(PyExc_ValueError,
                     "Board must be %d characters, got %zd",
                     BOARD_SIZE, board_len);
        return NULL;
    }

    int wc0 = PyObject_IsTrue(PyTuple_GetItem(wc_tuple, 0));
    int wc1 = PyObject_IsTrue(PyTuple_GetItem(wc_tuple, 1));
    int bc0 = PyObject_IsTrue(PyTuple_GetItem(bc_tuple, 0));
    int bc1 = PyObject_IsTrue(PyTuple_GetItem(bc_tuple, 1));

    if (PyErr_Occurred()) return NULL;

    /* Generate moves */
    CMove moves[MAX_MOVES];
    int count = gen_moves_internal(board, wc0, wc1, bc0, bc1, ep, kp,
                                   moves, MAX_MOVES);

    /* Score each move */
    ScoredMove scored[MAX_MOVES];
    int k;
    for (k = 0; k < count; k++) {
        scored[k].score = value_internal(board, ep, kp,
                                         moves[k].i, moves[k].j, moves[k].prom);
        scored[k].idx = k;
        scored[k].move = moves[k];
    }

    /* Sort descending by score */
    qsort(scored, count, sizeof(ScoredMove), scored_move_cmp);

    /* Build Python list of (score, (i, j, prom)) */
    PyObject *list = PyList_New(count);
    if (!list) return NULL;

    for (k = 0; k < count; k++) {
        PyObject *prom;
        if (scored[k].move.prom == '\0') {
            prom = g_empty_str;
            Py_INCREF(prom);
        } else {
            prom = g_prom_strs[(unsigned char)scored[k].move.prom];
            if (prom) {
                Py_INCREF(prom);
            } else {
                char buf[2] = { scored[k].move.prom, '\0' };
                prom = PyUnicode_FromString(buf);
                if (!prom) { Py_DECREF(list); return NULL; }
            }
        }

        PyObject *move_tuple = PyTuple_New(3);
        if (!move_tuple) { Py_DECREF(prom); Py_DECREF(list); return NULL; }
        PyTuple_SET_ITEM(move_tuple, 0, PyLong_FromLong(scored[k].move.i));
        PyTuple_SET_ITEM(move_tuple, 1, PyLong_FromLong(scored[k].move.j));
        PyTuple_SET_ITEM(move_tuple, 2, prom);

        PyObject *outer = PyTuple_New(2);
        if (!outer) { Py_DECREF(move_tuple); Py_DECREF(list); return NULL; }
        PyTuple_SET_ITEM(outer, 0, PyLong_FromLong(scored[k].score));
        PyTuple_SET_ITEM(outer, 1, move_tuple);

        PyList_SET_ITEM(list, k, outer);
    }

    return list;
}

/*
 * Swapcase lookup table: 'A'->'a', 'a'->'A', etc.
 * Non-alpha chars map to themselves.
 */
static char SWAPCASE[128];

static void init_swapcase(void) {
    int i;
    for (i = 0; i < 128; i++) {
        if (i >= 'A' && i <= 'Z')
            SWAPCASE[i] = (char)(i + 32);
        else if (i >= 'a' && i <= 'z')
            SWAPCASE[i] = (char)(i - 32);
        else
            SWAPCASE[i] = (char)i;
    }
}

/*
 * rotate_internal: reverse board and swapcase, negate score, swap castling,
 * flip ep/kp. Writes result into out_board[120].
 */
static void rotate_internal(
    const char *board, char *out_board,
    int score, int *out_score,
    int wc0, int wc1, int bc0, int bc1,
    int *out_wc0, int *out_wc1, int *out_bc0, int *out_bc1,
    int ep, int kp, int nullmove,
    int *out_ep, int *out_kp
) {
    /* Reverse + swapcase in one pass */
    int i;
    for (i = 0; i < BOARD_SIZE; i++) {
        out_board[i] = SWAPCASE[(unsigned char)board[BOARD_SIZE - 1 - i]];
    }
    *out_score = -score;
    /* Swap castling rights */
    *out_wc0 = bc0;
    *out_wc1 = bc1;
    *out_bc0 = wc0;
    *out_bc1 = wc1;
    /* Flip ep/kp */
    *out_ep = (ep && !nullmove) ? (119 - ep) : 0;
    *out_kp = (kp && !nullmove) ? (119 - kp) : 0;
}

/*
 * Python-callable rotate(board, score, wc, bc, ep, kp, nullmove)
 *   -> (board, score, wc, bc, ep, kp)
 */
static PyObject *py_rotate(PyObject *self, PyObject *args) {
    const char *board;
    Py_ssize_t board_len;
    int score;
    PyObject *wc_tuple, *bc_tuple;
    int ep, kp, nullmove;

    if (!PyArg_ParseTuple(args, "s#iOOiip",
                          &board, &board_len,
                          &score,
                          &wc_tuple, &bc_tuple,
                          &ep, &kp, &nullmove)) {
        return NULL;
    }

    if (board_len != BOARD_SIZE) {
        PyErr_Format(PyExc_ValueError,
                     "Board must be %d characters, got %zd",
                     BOARD_SIZE, board_len);
        return NULL;
    }

    int wc0 = PyObject_IsTrue(PyTuple_GetItem(wc_tuple, 0));
    int wc1 = PyObject_IsTrue(PyTuple_GetItem(wc_tuple, 1));
    int bc0 = PyObject_IsTrue(PyTuple_GetItem(bc_tuple, 0));
    int bc1 = PyObject_IsTrue(PyTuple_GetItem(bc_tuple, 1));
    if (PyErr_Occurred()) return NULL;

    char out_board[BOARD_SIZE];
    int out_score, out_wc0, out_wc1, out_bc0, out_bc1, out_ep, out_kp;

    rotate_internal(board, out_board, score, &out_score,
                    wc0, wc1, bc0, bc1,
                    &out_wc0, &out_wc1, &out_bc0, &out_bc1,
                    ep, kp, nullmove, &out_ep, &out_kp);

    PyObject *new_board = PyUnicode_FromStringAndSize(out_board, BOARD_SIZE);
    if (!new_board) return NULL;

    PyObject *new_wc = PyTuple_Pack(2,
        PyBool_FromLong(out_wc0), PyBool_FromLong(out_wc1));
    PyObject *new_bc = PyTuple_Pack(2,
        PyBool_FromLong(out_bc0), PyBool_FromLong(out_bc1));

    PyObject *result = PyTuple_Pack(6,
        new_board,
        PyLong_FromLong(out_score),
        new_wc, new_bc,
        PyLong_FromLong(out_ep),
        PyLong_FromLong(out_kp));

    Py_DECREF(new_board);
    Py_DECREF(new_wc);
    Py_DECREF(new_bc);

    return result;
}

/*
 * Python-callable move_and_rotate(board, score, wc, bc, ep, kp, mi, mj, prom)
 *   -> (board, score, wc, bc, ep, kp)
 *
 * Combines move() + value() + rotate() in one C call.
 * Works on a mutable char[120] buffer — no _put string copies.
 */
static PyObject *py_move_and_rotate(PyObject *self, PyObject *args) {
    const char *board;
    Py_ssize_t board_len;
    int score;
    PyObject *wc_tuple, *bc_tuple;
    int ep, kp, mi, mj;
    const char *prom_str;
    Py_ssize_t prom_len;

    if (!PyArg_ParseTuple(args, "s#iOOiiiis#",
                          &board, &board_len,
                          &score,
                          &wc_tuple, &bc_tuple,
                          &ep, &kp,
                          &mi, &mj,
                          &prom_str, &prom_len)) {
        return NULL;
    }

    if (board_len != BOARD_SIZE) {
        PyErr_Format(PyExc_ValueError,
                     "Board must be %d characters, got %zd",
                     BOARD_SIZE, board_len);
        return NULL;
    }

    int wc0 = PyObject_IsTrue(PyTuple_GetItem(wc_tuple, 0));
    int wc1 = PyObject_IsTrue(PyTuple_GetItem(wc_tuple, 1));
    int bc0 = PyObject_IsTrue(PyTuple_GetItem(bc_tuple, 0));
    int bc1 = PyObject_IsTrue(PyTuple_GetItem(bc_tuple, 1));
    if (PyErr_Occurred()) return NULL;

    char prom = (prom_len > 0) ? prom_str[0] : '\0';

    /* Compute new score: score + value(move) */
    int new_score = score + value_internal(board, ep, kp, mi, mj, prom);

    /* Work on a mutable copy */
    char buf[BOARD_SIZE];
    memcpy(buf, board, BOARD_SIZE);

    char p = buf[mi];
    /* Actual move */
    buf[mj] = buf[mi];
    buf[mi] = '.';

    /* Castling rights update — must match _update_castling(i, j, wc, bc) */
    int nwc0 = wc0, nwc1 = wc1, nbc0 = bc0, nbc1 = bc1;
    if (mi == A1) nwc0 = 0;         /* wc = (False, wc[1]) */
    if (mi == H1) nwc1 = 0;         /* wc = (wc[0], False) */
    if (mj == A8) nbc1 = 0;         /* bc = (bc[0], False) */
    if (mj == H8) nbc0 = 0;         /* bc = (False, bc[1]) */

    int new_ep = 0, new_kp = 0;

    /* Castling */
    if (IS_KING[(unsigned char)p]) {
        nwc0 = 0;
        nwc1 = 0;
        int diff = mj - mi;
        if (diff < 0) diff = -diff;
        if (diff == 2) {
            new_kp = (mi + mj) / 2;
            buf[mj < mi ? A1 : H1] = '.';
            buf[new_kp] = 'R';
        }
    }

    /* Pawn promotion, double move and en passant capture */
    if (IS_PAWN[(unsigned char)p]) {
        if (mj >= A8 && mj <= H8) {
            buf[mj] = prom;
        }
        if (mj - mi == 2 * DIR_N) {
            new_ep = mi + DIR_N;
        }
        if (mj == ep) {
            buf[mj + DIR_S] = '.';
        }
    }

    /* Now rotate: reverse + swapcase, negate score, swap castling, flip ep/kp */
    char rot_board[BOARD_SIZE];
    int rot_score, rot_wc0, rot_wc1, rot_bc0, rot_bc1, rot_ep, rot_kp;

    rotate_internal(buf, rot_board, new_score, &rot_score,
                    nwc0, nwc1, nbc0, nbc1,
                    &rot_wc0, &rot_wc1, &rot_bc0, &rot_bc1,
                    new_ep, new_kp, 0, &rot_ep, &rot_kp);

    /* Build Python result */
    PyObject *new_board = PyUnicode_FromStringAndSize(rot_board, BOARD_SIZE);
    if (!new_board) return NULL;

    PyObject *new_wc = PyTuple_Pack(2,
        PyBool_FromLong(rot_wc0), PyBool_FromLong(rot_wc1));
    PyObject *new_bc = PyTuple_Pack(2,
        PyBool_FromLong(rot_bc0), PyBool_FromLong(rot_bc1));

    PyObject *result = PyTuple_Pack(6,
        new_board,
        PyLong_FromLong(rot_score),
        new_wc, new_bc,
        PyLong_FromLong(rot_ep),
        PyLong_FromLong(rot_kp));

    Py_DECREF(new_board);
    Py_DECREF(new_wc);
    Py_DECREF(new_bc);

    return result;
}

/* Module method table */
static PyMethodDef SunfishCoreMethods[] = {
    {"gen_moves", py_gen_moves, METH_VARARGS,
     "Generate all pseudo-legal moves for a position.\n\n"
     "Args: board (str, 120 chars), wc (tuple), bc (tuple), ep (int), kp (int)\n"
     "Returns: list of (i, j, prom) tuples"},
    {"value", py_value, METH_VARARGS,
     "Compute positional score delta for a move.\n\n"
     "Args: board (str, 120 chars), ep (int), kp (int), i (int), j (int), prom (str)\n"
     "Returns: int score"},
    {"score_and_sort_moves", py_score_and_sort_moves, METH_VARARGS,
     "Generate, score, and sort all moves in one C call.\n\n"
     "Args: board (str, 120 chars), wc (tuple), bc (tuple), ep (int), kp (int)\n"
     "Returns: list of (score, (i, j, prom)) sorted descending"},
    {"rotate", py_rotate, METH_VARARGS,
     "Rotate board (reverse + swapcase), negate score, swap castling, flip ep/kp.\n\n"
     "Args: board (str), score (int), wc (tuple), bc (tuple), ep (int), kp (int), nullmove (bool)\n"
     "Returns: (board, score, wc, bc, ep, kp)"},
    {"move_and_rotate", py_move_and_rotate, METH_VARARGS,
     "Apply move, compute value, and rotate in one C call.\n\n"
     "Args: board (str), score (int), wc (tuple), bc (tuple), ep (int), kp (int), i (int), j (int), prom (str)\n"
     "Returns: (board, score, wc, bc, ep, kp)"},
    {NULL, NULL, 0, NULL}
};

/* Module definition */
static struct PyModuleDef sunfish_core_module = {
    PyModuleDef_HEAD_INIT,
    "_sunfish_core",
    "C extension for Sunfish chess engine hot paths",
    -1,
    SunfishCoreMethods
};

/* Module initialization */
PyMODINIT_FUNC PyInit__sunfish_core(void) {
    /* Initialize swapcase lookup table */
    init_swapcase();

    /* Pre-create singleton strings */
    g_empty_str = PyUnicode_InternFromString("");
    if (!g_empty_str) return NULL;

    /* Initialize all promotion string slots to NULL */
    memset(g_prom_strs, 0, sizeof(g_prom_strs));

    /* Pre-create promotion character strings */
    const char *prom_chars = "NBRQCDTXnbrqcdtx";
    const char *pc;
    for (pc = prom_chars; *pc; pc++) {
        char buf[2] = { *pc, '\0' };
        g_prom_strs[(unsigned char)*pc] = PyUnicode_InternFromString(buf);
        if (!g_prom_strs[(unsigned char)*pc]) return NULL;
    }

    PyObject *module = PyModule_Create(&sunfish_core_module);
    if (!module) return NULL;

    return module;
}
