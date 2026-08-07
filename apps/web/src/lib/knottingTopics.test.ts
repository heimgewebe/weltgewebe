import { describe, expect, it } from "vitest";
import {
  canonicalizeKnottingTopics,
  combineKnottingTags,
  KNOTTING_TOPICS,
  knottingTagDisplayLabel,
  knottingTopicTag,
  MAX_KNOTTING_TOPICS,
  prioritizeKnottingTopics,
  splitKnottingTags,
  toggleKnottingTopic,
  type KnottingTopic,
} from "./knottingTopics";

describe("knotting topics", () => {
  it("offers the canonical broad topic vocabulary", () => {
    expect(KNOTTING_TOPICS).toEqual([
      "Wohnen",
      "Ernährung",
      "Mobilität",
      "Energie",
      "Bildung",
      "Gesundheit",
      "Natur",
      "Kunst",
      "Handwerk",
      "Digitales",
      "Nachbarschaft",
      "Mitbestimmung",
    ]);
  });

  it("keeps at most four selected topics in canonical order", () => {
    let selected: KnottingTopic[] = [];
    for (const topic of ["Natur", "Wohnen", "Kunst", "Energie"] as const) {
      selected = toggleKnottingTopic(selected, topic);
    }

    expect(selected).toEqual(["Wohnen", "Energie", "Natur", "Kunst"]);
    expect(selected).toHaveLength(MAX_KNOTTING_TOPICS);
    expect(toggleKnottingTopic(selected, "Bildung")).toEqual(selected);
  });

  it("frees a slot and restores canonical order after arbitrary toggles", () => {
    let selected: KnottingTopic[] = ["Wohnen", "Energie", "Natur", "Kunst"];
    selected = toggleKnottingTopic(selected, "Natur");
    selected = toggleKnottingTopic(selected, "Bildung");
    selected = toggleKnottingTopic(selected, "Wohnen");
    selected = toggleKnottingTopic(selected, "Wohnen");

    expect(selected).toEqual(["Wohnen", "Energie", "Bildung", "Kunst"]);
  });

  it("uses stable machine tags independently from visible labels", () => {
    expect(knottingTopicTag("Ernährung")).toBe("thema:ernährung");
    expect(knottingTopicTag("Mobilität")).toBe("thema:mobilität");
    expect(knottingTagDisplayLabel("thema:ernährung")).toBe("Ernährung");
    expect(knottingTagDisplayLabel("Natur")).toBe("Natur");
  });

  it("normalizes selector values without case-folding free text", () => {
    expect(
      canonicalizeKnottingTopics(["  Ｋｕｎｓｔ ", "thema:natur"]),
    ).toEqual(["Natur", "Kunst"]);
    expect(canonicalizeKnottingTopics(["kunst", "thema:natur"])).toEqual([
      "Natur",
    ]);
  });

  it("preserves external topic overflow without letting it reclaim a slot", () => {
    const split = splitKnottingTags([
      "thema:kunst",
      "thema:energie",
      "thema:wohnen",
      "thema:bildung",
      "thema:natur",
      "Werkstatt",
      "Natur",
      "kunst",
    ]);

    expect(split.topics).toEqual(["Wohnen", "Energie", "Bildung", "Kunst"]);
    expect(split.keywords).toEqual([
      "thema:natur",
      "Werkstatt",
      "Natur",
      "kunst",
    ]);

    const roundTrip = combineKnottingTags(split.topics, split.keywords);
    expect(splitKnottingTags(roundTrip)).toEqual(split);
  });

  it("combines topics first while preserving distinct free keyword identities", () => {
    expect(
      combineKnottingTags(
        ["Natur", "Wohnen"],
        ["  Werkstatt  ", "Werkstatt", "natur", "Natur", "thema:natur"],
      ),
    ).toEqual(["thema:wohnen", "thema:natur", "Werkstatt", "natur", "Natur"]);
  });

  it("prioritizes controlled topics for the weave without rewriting legacy tags", () => {
    expect(
      prioritizeKnottingTopics([
        "Werkstatt",
        "thema:natur",
        "thema:kunst",
        "thema:wohnen",
        "offen",
      ]),
    ).toEqual([
      "thema:wohnen",
      "thema:natur",
      "thema:kunst",
      "Werkstatt",
      "offen",
    ]);

    expect(prioritizeKnottingTopics(["Natur", "Kunst", "Wohnen"])).toEqual([
      "Natur",
      "Kunst",
      "Wohnen",
    ]);
  });

  it("serializes the same selected set identically regardless of click order", () => {
    expect(combineKnottingTags(["Kunst", "Wohnen", "Natur"], [])).toEqual(
      combineKnottingTags(["Natur", "Kunst", "Wohnen"], []),
    );
  });
});
