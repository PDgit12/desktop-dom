import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { DesktopNode, ActionResult, DisplayInfo, SubregionCapture } from "./types.js";

const execFileAsync = promisify(execFile);

export class DesktopApp {
  readonly target: string;
  private cliBinary: string;

  constructor(target: string | number, cliBinary: string = "desktop-dom") {
    this.target = String(target);
    this.cliBinary = cliBinary;
  }

  static attach(target: string | number, cliBinary: string = "desktop-dom"): DesktopApp {
    return new DesktopApp(target, cliBinary);
  }

  /**
   * Retrieves the token-pruned semantic accessibility DOM.
   */
  async getTree(maxDepth: number = 10): Promise<DesktopNode> {
    const { stdout } = await execFileAsync(this.cliBinary, [
      "inspect",
      "--app",
      this.target,
      "--format",
      "json",
      "--depth",
      String(maxDepth),
    ]);
    return JSON.parse(stdout.trim()) as DesktopNode;
  }

  /**
   * Dispatches a deterministic hardware click to an element's centroid.
   */
  async click(elementId: string, button: "left" | "right" | "double" = "left"): Promise<ActionResult> {
    const { stdout } = await execFileAsync(this.cliBinary, [
      "click",
      "--app",
      this.target,
      "--id",
      elementId,
      "--button",
      button,
    ]);
    return { status: "success", action: "click", elementId, button, rawOutput: stdout.trim() };
  }

  /**
   * Types text using native OS keyboard events.
   */
  async type(text: string, elementId?: string, clearFirst: boolean = false): Promise<ActionResult> {
    const args = ["type-text", "--app", this.target, "--text", text];
    if (elementId) {
      args.push("--id", elementId);
    }
    if (clearFirst) {
      args.push("--clear");
    }
    const { stdout } = await execFileAsync(this.cliBinary, args);
    return { status: "success", action: "type", text, elementId, clearFirst, rawOutput: stdout.trim() };
  }

  /**
   * Dispatches keyboard shortcuts or modifier chords (e.g. 'cmd+s', 'return').
   */
  async press(keyCombination: string): Promise<ActionResult> {
    const { stdout } = await execFileAsync(this.cliBinary, ["press", "--key", keyCombination]);
    return { status: "success", action: "press", key: keyCombination, rawOutput: stdout.trim() };
  }

  /**
   * Checks whether the application window is present on the currently active virtual space.
   */
  async isOnActiveSpace(): Promise<boolean> {
    const { stdout } = await execFileAsync(this.cliBinary, ["spaces", "--app", this.target]);
    return stdout.includes("is visible on the current active virtual space");
  }
}
