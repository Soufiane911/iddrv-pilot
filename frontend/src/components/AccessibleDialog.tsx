import { useLayoutEffect, useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import './accessibleDialog.css';

/** Native modality makes the background inert; explicit cycling also supports DOM tests. */
export function AccessibleDialog({ children, className, labelledBy, describedBy, onClose, busy = false }: { children: ReactNode; className: string; labelledBy: string; describedBy?: string; onClose: () => void; busy?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null);
  const outsidePress = useRef(false);
  const outsideRelease = useRef(false);
  function isOutside(event: { currentTarget: HTMLDialogElement; clientX: number; clientY: number }) {
    const rect = event.currentTarget.getBoundingClientRect();
    return event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom;
  }
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useLayoutEffect(() => {
    const dialog = ref.current!;
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    // jsdom has no top-layer implementation; real browsers use native modality.
    if (typeof dialog.showModal === 'function') dialog.showModal();
    else dialog.setAttribute('open', '');
    const initial = dialog.querySelector<HTMLElement>('input:not(:disabled), select:not(:disabled), textarea:not(:disabled)') ?? dialog.querySelector<HTMLElement>('button:not(:disabled)');
    initial?.focus();
    return () => { dialog.close?.(); if (previous?.isConnected) previous.focus(); };
  }, []);
  return createPortal(<dialog ref={ref} className={`accessible-dialog ${className}`} aria-labelledby={labelledBy} aria-describedby={describedBy} aria-modal="true" tabIndex={-1} onPointerDown={event => {
    outsidePress.current = event.button === 0 && !busy && isOutside(event);
    outsideRelease.current = false;
  }} onPointerUp={event => {
    outsideRelease.current = event.button === 0 && !busy && isOutside(event);
  }} onPointerCancel={() => { outsidePress.current = false; outsideRelease.current = false; }} onClick={event => {
    const dismiss = outsidePress.current && outsideRelease.current && isOutside(event);
    outsidePress.current = false;
    outsideRelease.current = false;
    if (dismiss && !busy) closeRef.current();
  }} onCancel={event => { event.preventDefault(); if (!busy) closeRef.current(); }} onKeyDown={event => {
    if (event.key === 'Escape') { event.preventDefault(); if (!busy) closeRef.current(); }
    if (event.key !== 'Tab') return;
    const elements = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('button, input, select, textarea, a[href], [tabindex]')).filter(element => !element.matches(':disabled, [hidden], [tabindex="-1"]') && !element.closest('[hidden]'));
    const first = elements[0], last = elements[elements.length - 1];
    if (!first) { event.preventDefault(); event.currentTarget.focus(); }
    else if (event.shiftKey && (document.activeElement === first || document.activeElement === event.currentTarget)) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && (document.activeElement === last || document.activeElement === event.currentTarget)) { event.preventDefault(); first.focus(); }
  }}>{children}</dialog>, document.body);
}
