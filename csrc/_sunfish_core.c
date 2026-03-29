#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "_sunfish_core.h"

/* Pre-created Python string objects for promotion chars and empty string */
static PyObject *g_empty_str = NULL;
static PyObject *g_prom_strs[128]; /* indexed by char: 'N','B','R','Q','C','D','T','X' */

/* Internal move struct for stack-allocated buffer */
typedef struct {
    int i;
    int j;
    char prom; /* '\0' for no promotion */
} CMove;

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

/* Module method table */
static PyMethodDef SunfishCoreMethods[] = {
    {"gen_moves", py_gen_moves, METH_VARARGS,
     "Generate all pseudo-legal moves for a position.\n\n"
     "Args: board (str, 120 chars), wc (tuple), bc (tuple), ep (int), kp (int)\n"
     "Returns: list of (i, j, prom) tuples"},
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
