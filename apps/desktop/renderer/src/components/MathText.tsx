import 'katex/dist/katex.min.css';

import katex from 'katex';
import { Fragment, useLayoutEffect, useRef } from 'react';

import styles from './MathText.module.css';

export interface TextPart {
  math: boolean;
  text: string;
}

/**
 * Split lesson text into prose and inline mathematics. Mathematics is whatever
 * sits between a pair of dollar signs; a dollar sign without a partner is
 * ordinary text.
 */
export function splitMath(text: string): TextPart[] {
  const pieces = text.split('$');
  // An even number of pieces means an odd number of dollar signs: the last one has
  // no partner, so it and what follows go back into the prose before it.
  if (pieces.length % 2 === 0) {
    const tail = pieces.pop() ?? '';
    const before = pieces.pop() ?? '';
    pieces.push(`${before}$${tail}`);
  }
  return pieces
    .map((piece, index) => ({ math: index % 2 === 1, text: piece }))
    .filter((part) => part.text !== '');
}

function Formula({ tex }: { tex: string }) {
  const ref = useRef<HTMLSpanElement>(null);

  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return;
    try {
      // `render` builds DOM nodes and sets styles through the CSSOM, which the app's
      // Content Security Policy allows; an HTML string with style attributes would not be.
      katex.render(tex, element, {
        throwOnError: true,
        output: 'htmlAndMathml',
        strict: 'ignore',
        trust: false,
        maxExpand: 200,
      });
    } catch {
      // Show what was written rather than nothing or an error.
      element.textContent = tex;
    }
  }, [tex]);

  return <span ref={ref} className={styles.formula} />;
}

/**
 * Lesson text that may contain inline mathematics between dollar signs, such as
 * `The sum is $w_1 x_1 + b$.` Everything else is shown exactly as written:
 * nothing in the text is interpreted as markup.
 */
export function MathText({ text }: { text: string }) {
  return (
    <>
      {splitMath(text).map((part, index) =>
        part.math ? (
          <Formula key={index} tex={part.text} />
        ) : (
          <Fragment key={index}>{part.text}</Fragment>
        ),
      )}
    </>
  );
}
