import svgwrite

FILENAME = "Lineage.svg"
DRAWING_SIZE = 400
CIRCLE_SIZE = 50
CIRCLE_FILL_COLOR = "#3b82f6"
CIRCLE_STROKE_COLOR = "#1e3a8a"
CIRCLE_STROKE_WIDTH = 3
FONT_COLOR = "white"
FONT_SIZE = "12px"
FONT_FAMILY = "Arial, sans-serif"
FONT_WEIGHT = "bold"
LINE_STROKE_COLOR = "#374151"
LINE_STROKE_WIDTH = 4

class Lineage:
    def __init__(self):
        self.members: list[Mason] = []
        self.drawing: svgwrite.Drawing | None = None

    def add(self, mason: Mason):
        mason.lineage = self
        self.members.append(mason)

    def draw(self):
        # Create the drawing (canvas)
        self.drawing = svgwrite.Drawing(
            filename=FILENAME,
            size=(f"{DRAWING_SIZE}px", f"{DRAWING_SIZE}px"),
            viewBox=f"0 0 {DRAWING_SIZE} {DRAWING_SIZE}",
        )

        # Make a white background
        self.drawing.add(
            self.drawing.rect(
                insert=(0, 0),
                size=("100%", "100%"),
                fill="white",
            )
        )

        # Draw the lineage of all the Masons
        # FIXME: Stupid workaround3
        x = 0
        for mason in self.members:
            mason.draw(100+x, 100)
            x = 200

        # Save the drawing
        self.drawing.save(pretty=True)
        print(f"Saved {FILENAME}")

class Mason:
    def __init__(self, name: str, worshipful: bool = True, parent: Mason | None = None) -> None:
        self.name = name
        self.past_master = worshipful
        self.parent = parent
        self.x = None
        self.y = None
        self.lineage: Lineage | None = None
        if worshipful: self.name = "WB " + self.name
            
    def draw(self, x: int, y: int) -> None:
        assert self.lineage is not None
        drawing = self.lineage.drawing
        assert drawing is not None

        self.x = x
        self.y = y
        # Add shape
        drawing.add(
            drawing.circle(
                center=(x, y),
                r=CIRCLE_SIZE,
                fill=CIRCLE_FILL_COLOR,
                stroke=CIRCLE_STROKE_COLOR,
                stroke_width=CIRCLE_STROKE_WIDTH
            )
        )
        # Add text
        drawing.add(
            drawing.text(
                self.name,
                insert=(x, y),
                text_anchor="middle",
                dominant_baseline="middle",
                fill=FONT_COLOR,
                font_size=FONT_SIZE,
                font_family=FONT_FAMILY,
                font_weight=FONT_WEIGHT,
            )
        )
        # Add line, if needed (if there's a parent)
        if self.parent:
            drawing.add(
                drawing.line(
                    start=(self.x, self.y),
                    end=(self.parent.x, self.parent.y),
                    stroke=LINE_STROKE_COLOR,
                    stroke_width=LINE_STROKE_WIDTH,
                )
            )

if __name__ == "__main__":
    lineage = Lineage()
    joe = Mason("Joseph Shoulak", False)
    lineage.add(joe)
    jacob = Mason("Jacob Shoulak", False, joe)
    lineage.add(jacob)
    lineage.draw()