import {beforeEach,describe,expect,it} from 'vitest';
import {detectLang,translate} from './i18n';
import {WORKSPACE_STRINGS} from './workspaceStrings';
describe('multilingual app defaults and workspace',()=>{
 beforeEach(()=>localStorage.clear());
 it('opens in English and preserves an explicit language preference',()=>{expect(detectLang()).toBe('en');localStorage.setItem('zusage.lang','it');expect(detectLang()).toBe('it');localStorage.setItem('zusage.lang','invalid');expect(detectLang()).toBe('en');});
 it.each(['de','fr','it'] as const)('translates the core new screens into %s',lang=>{for(const source of ['Writing studio','Apertus connection','Your next chapter','A quick tour of Zusage','Password & recovery','Import & export']){expect(translate(lang,source)).not.toBe(source);}});
 it('preserves interpolation and contains no em dash in new translations',()=>{expect(translate('de','Welcome to Zusage, {name}!',{name:'Lea'})).toContain('Lea');expect(JSON.stringify(WORKSPACE_STRINGS)).not.toContain('\u2014');});
});
