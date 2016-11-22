#!/usr/bin/python
# -*- coding: utf-8 -*-
import unittest
import numpy as np

from misura.droid import data
from misura.canon import csutil

rd = np.random.random

print 'Importing', __name__


def setUpModule():
    print 'Starting', __name__


class CircularBuffer(unittest.TestCase):
    N = 50
    d = np.arange(N)
    t = np.arange(N) / 2.
    lst = np.array([t, d]).transpose()
    cb = data.CircularBuffer(N)

    def testAppend(self):
        self.cb.idx = 0
        for t, d in self.lst:
            self.cb.append([t, d])
        self.assertEqual(len(self.cb), self.N)
        self.assertEqual(self.cb.idx, 0)

    def testShift(self):
        """Controlla lo shifting ed il __getitem__"""
        self.cb.idx = 5
        self.assertEqual(self.cb.shift(
            0), 6, msg="Errore di shift sul piu' antico. real=%i, teor=%i" % (self.cb.shift(0), 6))
        self.assertEqual(self.cb.shift(
            1), 7, msg="Errore di shift sul secondo piu' antico. real=%i, teor=%i" % (self.cb.shift(1), 7))
        self.assertEqual(self.cb.shift(2), 8)
        self.assertEqual(
            self.cb.shift(-1), 5, msg="Errore di shift sul piu' recente. real=%i, teor=%i" % (self.cb.shift(-1), 5))
        self.assertEqual(
            self.cb.shift(-2), 4, msg="Errore di shift sul penultimo. real=%i, teor=%i" % (self.cb.shift(-2), 4))
        self.assertEqual(self.cb.shift(-6), 0)
        self.assertEqual(self.cb.shift(-7), self.N - 1)
        self.assertEqual(self.cb.shift(-8), self.N - 2)
        self.assertEqual(self.cb.shift(-self.N), 6)
        self.cb.idx = 0
        self.assertEqual(self.cb.shift(-1), 0)
        self.assertEqual(self.cb.shift(-2), self.N - 1)
        self.assertEqual(self.cb.shift(-3), self.N - 2)
        for i in range(-self.N, self.N):  # i e' indice relativo
            i2 = self.cb.shift(i)  # i2 e' indice assoluto
            t2 = self.cb.times[i2]
            t = self.cb[i][0]
            self.assertEqual(t, t2,  msg="DeShifting problem i=%i, i2=%i, idx=%i, t=%.1f, t2=%.1f" % (
                i, i2, self.cb.idx, t, t2))
            self.cb.idx = self.cb.shift(1)

    def testDeShift(self):
        """Controlla il deshifting"""
        self.cb.idx = 0
        for i in range(1,  self.N):  # i e' indice assoluto
            i2 = self.cb.deshift(i)  # i2 e' indice relativo
            t = self.cb.times[i]
            t2 = self.cb[i2][0]
            self.assertEqual(t, t2,  msg="Shifting problem i=%i, i2=%i, idx=%i, t=%.1f, t2=%.1f" % (
                i, i2, self.cb.idx, t, t2))
            self.cb.idx = self.cb.shift(1)

    def testSlicing(self):
        # significa che l'ultimo elemento aggiunto e' quello con indice zero
        # sulla lista
        self.cb.idx = 0
        return
        for n in range(-self.N, self.N):
            self.cb.idx = int(rd() * self.N)
            end = int(n + rd() * self.N)
            if n == 3:
                end = 3  # test slice nulla
            if n == 5:
                end = 2  # test slice inversa
            sl = self.cb[n:end]
            if n == end:
                self.assertEqual(len(sl), 0)
                continue
            if type(sl[0]) != type([]):
                sl = [sl]
            real = sl[0][0]
            teor = self.cb[n][0]
            self.assertEqual(sl[0][0], self.cb[n][0], msg="L'inizio della slice non corrisponde. start=%i, end=%i, real=%.1f, teor=%.1f"
                             % (n, end, real, teor))
            continue
            self.assertEqual(
                sl[-1][0], self.cb[end + 1][0], msg="La fine della slice non corrisponde. %i" % (end))

    def testEmptySlicing(self):
        cb = data.CircularBuffer(5)
        r = cb[-3:-2]
        self.assertEqual(r, [])

    def testSlicingExtreme(self):
        print 'slicingextreme'
        self.cb.idx = 5
        self.assertEqual(len(self.cb[-1:]), 1)
        self.assertEqual(len(self.cb[-2:]), 2)
        self.assertEqual(len(self.cb[-3:]), 3)
        self.assertEqual(len(self.cb[-4:]), 4)
        self.assertEqual(len(self.cb[0:0]), 0)
        self.assertEqual(len(self.cb[1:-1]), self.N - 2)
        self.assertEqual(len(self.cb[-self.N + 1:]), self.N - 1)
        self.assertEqual(len(self.cb[-self.N + 2:]), self.N - 2)
        r = self.cb[-self.N:]
        self.assertEqual(len(
            r), self.N, msg='Restituita lista errata quando richiesta esattamente tutta la lunghezza nel passato. real=%i, teor=%i' % (len(r), self.N))
        r = self.cb[-self.N - 10:]
        self.assertEqual(len(
            r), self.N, msg='Restituita lista errata quando la richiesta nel passato eccede la lunghezza. real=%i, teor=%i' % (len(r), self.N))

    def testGetTimeExtreme(self):
        """Verifica gli estremi della ricerca temporale"""
        self.cb.idx = 10
        i = self.cb.get_time(self.t[-1] + 1)
        self.assertEqual(self.cb[i][0], self.t[-1], msg="La ricerca di un punto nel futuro non restituisce il punto piu recente. i=%i, teor=%.2f, real=%.2f"
                         % (i, self.cb[i][0], self.t[-1]))
        i = self.cb.get_time(self.t[0] - 1)
        self.assertEqual(self.cb[i][0], self.t[0], msg="La ricerca di un punto nel passato non restituisce il punto piu antico. i=%i, teor=%.2f, real=%.2f"
                         % (i, self.cb[i][0], self.t[0]))

    def test_get_time(self):
        """Time search"""
        self.cb.idx = 0
        for n in range(-self.N, self.N):
            req = rd() * self.N / 2.
            req = 7
            i = self.cb.get_time(req)
            i2 = csutil.find_nearest_brute(self.cb.times, req)
            self.assertEqual(self.cb[i][0], self.cb.times[i2],
                             msg='i=%i, i2=%i, sh=%i, idx=%i, %.2f, %.2f' %
                             (i, i2, self.cb.shift(i), self.cb.idx, self.cb[i][0], self.cb.times[i2]))
            # Errori nel tempo restituito:
            ti = self.cb[i][0]
            val = abs(ti - req)  # all'indice i
            valPlus1 = abs(self.cb[i - 1][0] - req)  # all'indice successivo
            valMinus1 = abs(self.cb[i + 1][0] - req)  # all'indice precedente
            # Se get_time funziona bene, gli errori generati dall'indice successivo
            # e precedente devono entrambi essere inferiori rispetto ad i
            self.assertTrue(
                val <= valPlus1, msg='%.2f, %.1f,%i, %.2f, %.2f' % (req, ti, i, val, valPlus1))
            self.assertTrue(val <= valMinus1, msg='%.2f, %.1f, %i, %.2f, %.2f' % (
                req, ti, i, val, valMinus1))
            self.cb.idx = self.cb.shift(1)

    def testOverAppend(self):
        """Controlla che appendendo oltre la lunghezza del buffer non si generino errori."""
        Nd = int(self.N / 2)
        N1 = 3 * self.N + Nd
        d = np.arange(N1)
        t = np.arange(N1) / 2.
        lst = np.array([t, d]).transpose()
        self.cb.idx = 0
        for i, n in enumerate(d):
            self.cb.append([n / 2., n])
        s = Nd - 5
        ti = self.cb.get_time(t[-s])
        self.assertEqual(self.cb[ti][0], t[-s])
        sl = self.cb[ti:]
        ls = lst[-s:]
        self.assertEqual(sl[0][0],	ls[0][0])
        self.assertEqual(sl[-1][0],	ls[-1][0])


if __name__ == "__main__":
    unittest.main()
