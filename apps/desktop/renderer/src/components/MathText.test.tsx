import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { MathText, splitMath } from './MathText';

describe('splitMath', () => {
  it('separates prose from mathematics between dollar signs', () => {
    expect(splitMath('The sum is $w_1 x_1 + b$, then $z$.')).toEqual([
      { math: false, text: 'The sum is ' },
      { math: true, text: 'w_1 x_1 + b' },
      { math: false, text: ', then ' },
      { math: true, text: 'z' },
      { math: false, text: '.' },
    ]);
  });

  it('leaves text without mathematics alone', () => {
    expect(splitMath('A neuron adds things up.')).toEqual([
      { math: false, text: 'A neuron adds things up.' },
    ]);
    expect(splitMath('')).toEqual([]);
  });

  it('treats a dollar sign without a partner as ordinary text', () => {
    expect(splitMath('It costs $5 a day.')).toEqual([{ math: false, text: 'It costs $5 a day.' }]);
    expect(splitMath('$a$ and then $b')).toEqual([
      { math: true, text: 'a' },
      { math: false, text: ' and then $b' },
    ]);
  });

  it('skips empty mathematics', () => {
    expect(splitMath('$$')).toEqual([]);
    expect(splitMath('Before $$ after')).toEqual([
      { math: false, text: 'Before ' },
      { math: false, text: ' after' },
    ]);
  });
});

describe('MathText', () => {
  it('typesets the mathematics and keeps the prose as plain text', () => {
    const { container } = render(
      <p>
        <MathText text="Compute $w_1 x_1 + b$ by hand." />
      </p>,
    );
    expect(container.textContent).toContain('Compute ');
    expect(container.textContent).toContain(' by hand.');
    expect(container.querySelectorAll('.katex')).toHaveLength(1);
    // The source is kept for assistive technology and for copying.
    expect(container.querySelector('annotation')?.textContent).toBe('w_1 x_1 + b');
  });

  it('shows what was written when the mathematics cannot be typeset', () => {
    const { container } = render(
      <p>
        <MathText text="Broken: $\frac{1$ here." />
      </p>,
    );
    expect(container.querySelector('.katex')).toBeNull();
    expect(container.textContent).toBe('Broken: \\frac{1 here.');
  });

  it('never treats lesson text as markup', () => {
    const { container } = render(
      <p>
        <MathText text={'<img src=x onerror="alert(1)"> and $x$'} />
      </p>,
    );
    expect(container.querySelector('img')).toBeNull();
    expect(container.textContent).toContain('<img src=x onerror="alert(1)">');
  });

  it('refuses commands that could reach outside the page', () => {
    const { container } = render(
      <p>
        <MathText text={'$\\href{https://example.com}{x}$'} />
      </p>,
    );
    expect(container.querySelector('a')).toBeNull();
  });
});
