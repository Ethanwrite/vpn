import { useId } from "react";
import { SICKLE, HAMMER } from "./EmblemPaths";
export default function EmblemGraphic({ animated = false, className }: { animated?: boolean; className?: string }) {
  const id = useId();
  const hammerClass = animated ? "em-part em-hammer" : undefined;
  return <svg className={className} viewBox="0 0 200 200" aria-hidden="true" fill="none" stroke="#922D28" strokeWidth="4.5" strokeLinecap="round" strokeLinejoin="round">
    <defs><mask id={id} maskUnits="userSpaceOnUse" x="-20" y="-20" width="240" height="240">
      <rect x="-20" y="-20" width="240" height="240" fill="white" stroke="none"/>
      <g className={hammerClass} fill="black" stroke="black">{HAMMER.map(d => <path key={d} d={d}/>)}</g>
    </mask></defs>
    <g mask={`url(#${id})`}><g className={animated ? "em-part em-sickle" : undefined}>{SICKLE.map(d => <path key={d} d={d}/>)}</g></g>
    <g className={hammerClass}>{HAMMER.map(d => <path key={d} d={d}/>)}</g>
  </svg>;
}
