import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "rdd_to_yolo", Path(__file__).parent.parent / "scripts" / "rdd_to_yolo.py"
)
rdd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rdd)

XML = """<annotation><size><width>720</width><height>720</height></size>
<object><name>D40</name><bndbox><xmin>100</xmin><ymin>200</ymin><xmax>200</xmax><ymax>300</ymax></bndbox></object>
<object><name>D00</name><bndbox><xmin>1</xmin><ymin>1</ymin><xmax>50</xmax><ymax>50</ymax></bndbox></object>
</annotation>"""


def test_only_potholes_kept_and_normalised(tmp_path):
    f = tmp_path / "a.xml"
    f.write_text(XML)
    lines = rdd.parse_xml(f)
    assert len(lines) == 1
    cls, cx, cy, w, h = lines[0].split()
    assert cls == "0"
    assert abs(float(cx) - 150 / 720) < 1e-5
    assert abs(float(cy) - 250 / 720) < 1e-5
    assert abs(float(w) - 100 / 720) < 1e-5


def test_missing_size_returns_none(tmp_path):
    f = tmp_path / "b.xml"
    f.write_text("<annotation><object><name>D40</name></object></annotation>")
    assert rdd.parse_xml(f) is None
