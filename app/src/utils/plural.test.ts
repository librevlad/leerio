import { describe, it, expect } from 'vitest'
import { plural } from './plural'

describe('plural', () => {
  const one = 'книга'
  const few = 'книги'
  const many = 'книг'

  describe('one form (mod10=1, mod100≠11)', () => {
    it('n=1', () => {
      expect(plural(1, one, few, many)).toBe(one)
    })

    it('n=21', () => {
      expect(plural(21, one, few, many)).toBe(one)
    })

    it('n=31', () => {
      expect(plural(31, one, few, many)).toBe(one)
    })

    it('n=101', () => {
      expect(plural(101, one, few, many)).toBe(one)
    })

    it('n=121', () => {
      expect(plural(121, one, few, many)).toBe(one)
    })

    it('n=1001', () => {
      expect(plural(1001, one, few, many)).toBe(one)
    })
  })

  describe('few form (mod10=2-4, mod100 not 12-14)', () => {
    it('n=2', () => {
      expect(plural(2, one, few, many)).toBe(few)
    })

    it('n=3', () => {
      expect(plural(3, one, few, many)).toBe(few)
    })

    it('n=4', () => {
      expect(plural(4, one, few, many)).toBe(few)
    })

    it('n=22', () => {
      expect(plural(22, one, few, many)).toBe(few)
    })

    it('n=23', () => {
      expect(plural(23, one, few, many)).toBe(few)
    })

    it('n=24', () => {
      expect(plural(24, one, few, many)).toBe(few)
    })

    it('n=32', () => {
      expect(plural(32, one, few, many)).toBe(few)
    })

    it('n=102', () => {
      expect(plural(102, one, few, many)).toBe(few)
    })

    it('n=1002', () => {
      expect(plural(1002, one, few, many)).toBe(few)
    })
  })

  describe('many form (mod10=0,5-9 or mod100=11-14)', () => {
    it('n=0', () => {
      expect(plural(0, one, few, many)).toBe(many)
    })

    it('n=5', () => {
      expect(plural(5, one, few, many)).toBe(many)
    })

    it('n=6', () => {
      expect(plural(6, one, few, many)).toBe(many)
    })

    it('n=9', () => {
      expect(plural(9, one, few, many)).toBe(many)
    })

    it('n=10', () => {
      expect(plural(10, one, few, many)).toBe(many)
    })

    it('n=15', () => {
      expect(plural(15, one, few, many)).toBe(many)
    })

    it('n=20', () => {
      expect(plural(20, one, few, many)).toBe(many)
    })

    it('n=100', () => {
      expect(plural(100, one, few, many)).toBe(many)
    })

    it('n=1000', () => {
      expect(plural(1000, one, few, many)).toBe(many)
    })
  })

  describe('special case: mod100=11-14 → many (not one/few)', () => {
    it('n=11 (not one despite mod10=1)', () => {
      expect(plural(11, one, few, many)).toBe(many)
    })

    it('n=12 (not few despite mod10=2)', () => {
      expect(plural(12, one, few, many)).toBe(many)
    })

    it('n=13 (not few despite mod10=3)', () => {
      expect(plural(13, one, few, many)).toBe(many)
    })

    it('n=14 (not few despite mod10=4)', () => {
      expect(plural(14, one, few, many)).toBe(many)
    })

    it('n=111 (mod100=11)', () => {
      expect(plural(111, one, few, many)).toBe(many)
    })

    it('n=112 (mod100=12)', () => {
      expect(plural(112, one, few, many)).toBe(many)
    })

    it('n=113 (mod100=13)', () => {
      expect(plural(113, one, few, many)).toBe(many)
    })

    it('n=114 (mod100=14)', () => {
      expect(plural(114, one, few, many)).toBe(many)
    })

    it('n=211 (mod100=11)', () => {
      expect(plural(211, one, few, many)).toBe(many)
    })
  })

  describe('range n=5-20 → many', () => {
    it.each([5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20])(
      'n=%i → many',
      (n) => {
        expect(plural(n, one, few, many)).toBe(many)
      },
    )
  })

  describe('negative numbers (uses Math.abs)', () => {
    it('n=-1 → one', () => {
      expect(plural(-1, one, few, many)).toBe(one)
    })

    it('n=-2 → few', () => {
      expect(plural(-2, one, few, many)).toBe(few)
    })

    it('n=-5 → many', () => {
      expect(plural(-5, one, few, many)).toBe(many)
    })

    it('n=-11 → many', () => {
      expect(plural(-11, one, few, many)).toBe(many)
    })

    it('n=-21 → one', () => {
      expect(plural(-21, one, few, many)).toBe(one)
    })

    it('n=-111 → many', () => {
      expect(plural(-111, one, few, many)).toBe(many)
    })
  })

  describe('large numbers', () => {
    it('n=111 → many (mod100=11)', () => {
      expect(plural(111, one, few, many)).toBe(many)
    })

    it('n=121 → one (mod10=1, mod100=21)', () => {
      expect(plural(121, one, few, many)).toBe(one)
    })

    it('n=1001 → one', () => {
      expect(plural(1001, one, few, many)).toBe(one)
    })

    it('n=1011 → many (mod100=11)', () => {
      expect(plural(1011, one, few, many)).toBe(many)
    })

    it('n=10002 → few', () => {
      expect(plural(10002, one, few, many)).toBe(few)
    })

    it('n=10011 → many', () => {
      expect(plural(10011, one, few, many)).toBe(many)
    })
  })

  describe('NaN/Infinity edge cases', () => {
    it('NaN → many (fallback)', () => {
      expect(plural(NaN, one, few, many)).toBe(many)
    })

    it('Infinity → many (fallback)', () => {
      expect(plural(Infinity, one, few, many)).toBe(many)
    })

    it('-Infinity → many (fallback)', () => {
      expect(plural(-Infinity, one, few, many)).toBe(many)
    })
  })
})
