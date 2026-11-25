import { readFileSync } from 'node:fs';
import { compile } from '@mdx-js/mdx';

const input = readFileSync(0, 'utf8');
const frontmatter = /^---\ntitle: ("[^\n]*")\nlang: (de|en)\n---\n\n/u.exec(input);
if (!frontmatter || typeof JSON.parse(frontmatter[1]) !== 'string') process.exit(1);
await compile(input.slice(frontmatter[0].length));
