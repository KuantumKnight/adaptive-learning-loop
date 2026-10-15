import { useState } from "react";
import type { Lesson } from "./api";

export default function AlgorithmVisualizer({
  config,
  preview = false,
}: {
  config: NonNullable<Lesson["visualizer"]>;
  preview?: boolean;
}) {
  const [values, setValues] = useState(config.values);
  const [input, setInput] = useState(config.values.join(", "));
  const [target, setTarget] = useState(
    String(config.target ?? config.values[0]),
  );
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [linearIndex, setLinearIndex] = useState(0);
  const [binaryBounds, setBinaryBounds] = useState({
    low: 0,
    high: config.values.length - 1,
  });
  const [bubbleCursor, setBubbleCursor] = useState({ pass: 0, index: 0 });
  const [message, setMessage] = useState("Ready to trace");
  const [stepCount, setStepCount] = useState(0);
  const [swaps, setSwaps] = useState(0);
  const [passSwapped, setPassSwapped] = useState(false);
  const [outcome, setOutcome] = useState<"running" | "found" | "not-found" | "sorted">("running");
  const kind = config.kind;

  function reset(nextValues = config.values) {
    setValues(nextValues);
    setInput(nextValues.join(", "));
    setLinearIndex(0);
    setBinaryBounds({ low: 0, high: nextValues.length - 1 });
    setBubbleCursor({ pass: 0, index: 0 });
    setActiveIndex(null);
    setMessage("Ready to trace");
    setStepCount(0);
    setSwaps(0);
    setPassSwapped(false);
    setOutcome("running");
  }

  function applyInput() {
    const parts = input.split(",").map((item) => item.trim());
    const parsed = parts.map(Number);
    if (!parts.length || parts.length > 20 || parts.some((part) => part === "") || parsed.some((value) => !Number.isFinite(value))) {
      setMessage("Enter 1–20 valid numbers separated by commas; every value is required.");
      return;
    }
    if (
      kind === "binary" &&
      parsed.some((value, index) => index > 0 && parsed[index - 1] > value)
    ) {
      setMessage("Binary search needs sorted values. Sort the sample, then use it.");
      return;
    }
    reset(parsed);
  }

  function advance() {
    if (outcome !== "running") return;
    const numericTarget = Number(target);
    if (!values.length || (kind !== "bubble" && (target.trim() === "" || !Number.isFinite(numericTarget)))) {
      setMessage("Enter a numeric target before stepping");
      return;
    }
    if (kind === "binary") {
      const { low, high } = binaryBounds;
      if (low > high) {
        setActiveIndex(null);
        setOutcome("not-found");
        setMessage("Bounds crossed: target is not in the list");
        return;
      }
      const middle = Math.floor((low + high) / 2);
      const value = values[middle];
      setStepCount((count) => count + 1);
      setActiveIndex(middle);
      if (value === numericTarget) {
        setOutcome("found");
        setMessage(
          `low ${low}, middle ${middle}, high ${high}: found ${numericTarget}`,
        );
        setBinaryBounds({ low, high: middle - 1 });
        return;
      }
      if (numericTarget > value) {
        setMessage(
          `low ${low}, middle ${middle}, high ${high}: ${numericTarget} is larger, move low to ${middle + 1}`,
        );
        setBinaryBounds({ low: middle + 1, high });
        if (middle + 1 > high) setOutcome("not-found");
        return;
      }
      setMessage(
        `low ${low}, middle ${middle}, high ${high}: ${numericTarget} is smaller, move high to ${middle - 1}`,
      );
      setBinaryBounds({ low, high: middle - 1 });
      if (low > middle - 1) setOutcome("not-found");
      return;
    }
    if (kind === "bubble") {
      const { pass, index } = bubbleCursor;
      if (pass >= values.length - 1) {
        setActiveIndex(null);
        setOutcome("sorted");
        setMessage("No more passes: the list is sorted");
        return;
      }
      const next = [...values];
      setStepCount((count) => count + 1);
      const right = index + 1;
      const didSwap = next[index] > next[right];
      setActiveIndex(index);
      if (didSwap) {
        [next[index], next[right]] = [next[right], next[index]];
        setValues(next);
        setSwaps((count) => count + 1);
        setPassSwapped(true);
        setMessage(
          `Pass ${pass + 1}: compare positions ${index} and ${right}; swap`,
        );
      } else
        setMessage(
          `Pass ${pass + 1}: compare positions ${index} and ${right}; keep order`,
        );
      const nextIndex = right >= values.length - 1 - pass ? 0 : right;
      if (nextIndex === 0) {
        if (!passSwapped && !didSwap) {
          setOutcome("sorted");
          setMessage("A full pass needed no swaps: the list is sorted.");
        } else if (pass >= values.length - 2) setOutcome("sorted");
        setPassSwapped(false);
      }
      setBubbleCursor({
        pass: right >= values.length - 1 - pass ? pass + 1 : pass,
        index: nextIndex,
      });
      return;
    }
    if (linearIndex >= values.length) {
      setActiveIndex(null);
      setOutcome("not-found");
      setMessage(`Target ${numericTarget} was not found`);
      return;
    }
    const index = linearIndex;
    setStepCount((count) => count + 1);
    setActiveIndex(index);
    if (values[index] === numericTarget) {
      setOutcome("found");
      setMessage(`Check index ${index}: found ${numericTarget}`);
      setLinearIndex(values.length);
      return;
    }
    setMessage(
      `Check index ${index}: ${values[index]} is not ${numericTarget}; continue right`,
    );
    setLinearIndex(index + 1);
    if (index + 1 >= values.length) setOutcome("not-found");
  }

  return (
    <div className={`visualizer ${preview ? "visualizer-preview" : ""}`}>
      <div className="visualizer-head">
        <div>
          <span className="example-label">{preview ? "TRY IT · NO SESSION NEEDED" : "TRACE THE ALGORITHM"}</span>
          <strong>
            {kind === "binary"
              ? "Binary search bounds"
              : kind === "bubble"
                ? "Neighbor swaps"
                : "Left-to-right scan"}
          </strong>
        </div>
        <button className="ghost-button" onClick={() => reset()}>
          Reset
        </button>
      </div>
      <div className="value-row" aria-label="Algorithm values">
        {values.map((value, index) => (
          <span
            className={index === activeIndex ? "active-value" : ""}
            key={`${value}-${index}`}
          >
            {value}
          </span>
        ))}
      </div>
      <p className="trace-status">{stepCount} comparisons · {kind === "bubble" ? `${swaps} swaps · pass ${Math.min(bubbleCursor.pass + 1, values.length)}` : kind === "binary" ? `bounds ${binaryBounds.low}–${binaryBounds.high}` : `index ${Math.min(linearIndex, values.length)}`} · {outcome === "running" ? "in progress" : outcome.replace("-", " ")}</p>
      <div className="visualizer-controls">
        <label>
          Sample input
          <input
            aria-label="Sample input"
            value={input}
            onChange={(event) => setInput(event.target.value)}
          />
        </label>
        {kind !== "bubble" && (
          <label>
            Target
            <input
              aria-label="Target value"
              value={target}
              onChange={(event) => setTarget(event.target.value)}
            />
          </label>
        )}
        <button className="small-button" onClick={applyInput}>
          Use input
        </button>
        <button className="small-button" onClick={advance} disabled={outcome !== "running"}>
          Step →
        </button>
      </div>
      <p className="trace-message" aria-live="polite">
        {message}
      </p>
    </div>
  );
}
