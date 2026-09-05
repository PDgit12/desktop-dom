export type CanonicalRole =
  | "button"
  | "input"
  | "checkbox"
  | "radio"
  | "combobox"
  | "menuitem"
  | "menu"
  | "menubar"
  | "tab"
  | "tab_group"
  | "table"
  | "table_row"
  | "table_cell"
  | "text"
  | "link"
  | "image"
  | "slider"
  | "scrollbar"
  | "window"
  | "dialog"
  | "group"
  | "pane"
  | "unknown";

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface ElementStates {
  focused?: boolean;
  focusable?: boolean;
  editable?: boolean;
  clickable?: boolean;
  checked?: boolean | null;
  disabled?: boolean;
  expanded?: boolean | null;
  selected?: boolean | null;
}

export interface DesktopNode {
  id: string;
  role: CanonicalRole | string;
  name?: string;
  value?: string | null;
  bbox: [number, number, number, number] | BoundingBox;
  states?: ElementStates;
  children?: DesktopNode[];
}

export interface ActionResult {
  status: "success" | "error";
  action: string;
  [key: string]: any;
}

export interface DisplayInfo {
  id: number;
  name: string;
  is_primary: boolean;
  bounds: BoundingBox;
  scale_factor: number;
  is_active_space: boolean;
}

export interface SubregionCapture {
  element_id?: string | null;
  bbox: BoundingBox;
  image_base64: string;
  mime_type: string;
  width: number;
  height: number;
  estimated_tokens: number;
}
