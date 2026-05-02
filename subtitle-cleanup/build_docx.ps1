param(
    [Parameter(Mandatory=$true)][string]$InputTxt,
    [Parameter(Mandatory=$true)][string]$OutputDocx
)

# Build a .docx from a manifest-style text file whose each line is prefixed by
# a 3-char code + one space:
#   TIT <title>           centered bold 17pt title
#   OHD <text>            bold 13pt outline header (e.g. 纲要：)
#   OUT <text>            13pt outline item (一、xxx)
#   BOD <paragraph>       body paragraph, 13pt, first-line indent 2 chars
#   DIV <text>            centered divider line (U+2500 run)
#   BLK                   empty paragraph (spacer)
#
# Leading U+3000 full-width spaces in BOD lines are stripped — the indent is
# replaced by a real Word first-line indent.
#
# Font: 宋体 (East Asian) / Times New Roman (Latin), 13pt default, 1.5 line spacing.
# Page: left/right margins 0.32 cm (narrow); top/bottom 2.54 cm (default).

$ErrorActionPreference = "Stop"

$content = [System.IO.File]::ReadAllText($InputTxt, [System.Text.Encoding]::UTF8)
$lines = $content -split "`r?`n"

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$doc = $word.Documents.Add()

# Page setup
$ps = $doc.PageSetup
$ps.LeftMargin   = $word.CentimetersToPoints(0.32)
$ps.RightMargin  = $word.CentimetersToPoints(0.32)
$ps.TopMargin    = $word.CentimetersToPoints(2.54)
$ps.BottomMargin = $word.CentimetersToPoints(2.54)

# Default Normal style
$normal = $doc.Styles.Item("Normal")
$normal.Font.NameFarEast = "SimSun"
$normal.Font.NameAscii   = "Times New Roman"
$normal.Font.NameOther   = "Times New Roman"
$normal.Font.Size        = 13
$normal.ParagraphFormat.LineSpacingRule = 5   # wdLineSpace1pt5
$normal.ParagraphFormat.SpaceBefore     = 0
$normal.ParagraphFormat.SpaceAfter      = 0

# We drive the cursor with Selection, applying fresh style per paragraph.
$sel = $word.Selection

function Reset-Style {
    $sel.Font.Bold = $false
    $sel.Font.Size = 13
    $sel.ParagraphFormat.Alignment = 0   # wdAlignParagraphLeft
    $sel.ParagraphFormat.CharacterUnitFirstLineIndent = 0
}

$first = $true

foreach ($rawLine in $lines) {
    # Strip trailing CR (already split but defensive)
    $line = $rawLine.TrimEnd("`r")

    if ($line.Length -lt 3) { continue }
    $code = $line.Substring(0, 3)
    $text = if ($line.Length -gt 4) { $line.Substring(4) } else { "" }

    # Insert a newline before each paragraph except the very first.
    if (-not $first) { $sel.TypeParagraph() }
    $first = $false

    switch ($code) {
        "TIT" {
            Reset-Style
            $sel.ParagraphFormat.Alignment = 1   # wdAlignParagraphCenter
            $sel.Font.Bold = $true
            $sel.Font.Size = 17
            $sel.TypeText($text)
        }
        "OHD" {
            Reset-Style
            $sel.Font.Bold = $true
            $sel.TypeText($text)
        }
        "OUT" {
            Reset-Style
            $sel.TypeText($text)
        }
        "BOD" {
            Reset-Style
            # strip leading U+3000 spaces — real indent replaces them
            $stripped = $text -replace "^[　]+", ""
            if ($stripped.Length -gt 0) {
                $sel.ParagraphFormat.CharacterUnitFirstLineIndent = 2
                $sel.TypeText($stripped)
            }
        }
        "DIV" {
            Reset-Style
            $sel.ParagraphFormat.Alignment = 1
            $sel.TypeText($text)
        }
        "BLK" {
            Reset-Style
        }
        default {
            # Unknown code — treat as body pass-through without indent
            Reset-Style
            $sel.TypeText($line)
        }
    }
}

# Save as .docx (wdFormatXMLDocument = 12, or use 16 for default)
$doc.SaveAs([ref]$OutputDocx, [ref]16)
$doc.Close($false)
$word.Quit()

[System.Runtime.InteropServices.Marshal]::ReleaseComObject($sel) | Out-Null
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($doc) | Out-Null
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
[GC]::Collect()
[GC]::WaitForPendingFinalizers()

Write-Output "wrote $OutputDocx"
