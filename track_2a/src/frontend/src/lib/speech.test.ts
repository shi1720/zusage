import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { pickVoice, useTts } from "./speech";

const play = vi.fn().mockResolvedValue(undefined);
class AudioStub {
  src = ""; onended = null; onerror = null;
  play = play; pause = vi.fn(); load = vi.fn(); removeAttribute = vi.fn();
}
beforeEach(() => {
  vi.stubGlobal("Audio", AudioStub);
  vi.stubGlobal("speechSynthesis", { cancel: vi.fn(), getVoices: () => [], addEventListener: vi.fn(), removeEventListener: vi.fn(), speak: vi.fn() });
  vi.stubGlobal("SpeechSynthesisUtterance", class { constructor(public text: string) {} });
  vi.stubGlobal("URL", class extends URL { static createObjectURL = vi.fn(()=>"blob:voice"); static revokeObjectURL = vi.fn(); });
  play.mockClear();
});
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it("prefers a natural language voice over the first basic voice", () => {
  const voices = [{name:"Basic",lang:"en-GB"},{name:"Google UK English",lang:"en-GB"},{name:"Siri",lang:"fr-FR"}] as SpeechSynthesisVoice[];
  expect(pickVoice(voices,"en-GB")?.name).toBe("Google UK English");
  expect(pickVoice(voices,"it-CH")).toBeUndefined();
});

describe("natural playback", () => {
  it("plays and reuses private audio without a second synthesis request", async () => {
    const fetch = vi.fn().mockResolvedValue({ok:true,blob:async()=>new Blob(["audio"],{type:"audio/mpeg"})});
    vi.stubGlobal("fetch",fetch);
    const { result } = renderHook(()=>useTts("en","owned-interview",true));
    act(()=>result.current.speak("Tell me about yourself."));
    await waitFor(()=>expect(play).toHaveBeenCalledTimes(1));
    act(()=>result.current.speak("Tell me about yourself."));
    await waitFor(()=>expect(play).toHaveBeenCalledTimes(2));
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0][0]).toContain("/owned-interview/speech");
  });
  it("never starts late audio after Stop while synthesis is pending", async () => {
    let resolve!: (r:unknown)=>void;
    vi.stubGlobal("fetch",vi.fn(()=>new Promise(r=>{resolve=r;})));
    const { result } = renderHook(()=>useTts("en","owned-interview",true));
    act(()=>result.current.speak("Question"));
    act(()=>result.current.stop());
    await act(async()=>{resolve({ok:true,blob:async()=>new Blob(["audio"])});});
    expect(play).not.toHaveBeenCalled();
    expect(result.current.speaking).toBe(false);
  });
  it("labels a provider outage and allows device voice fallback", async () => {
    vi.stubGlobal("fetch",vi.fn().mockResolvedValue({ok:false,status:503}));
    const { result } = renderHook(()=>useTts("de","owned-interview",true));
    act(()=>result.current.speak("Hallo"));
    await waitFor(()=>expect(result.current.fallback).toBe(true));
    expect(play).not.toHaveBeenCalled();
  });
});
