@default: #B3B3B3;

Map {
  background-color: #000000;
}

#invasive {
  marker-width: 2;
  /* marker-fill: @default; */
  marker-line-width: 0;
  marker-line-color: transparent;
  marker-allow-overlap: true;
  marker-opacity: 0.6;
}
#invasive {
  [zoom > 9][zoom <= 6]   { marker-width: 2; }
  [zoom > 6][zoom <= 8]   { marker-width: 4; }
  [zoom > 8][zoom <= 10]  { marker-width: 7; }
  [zoom > 10][zoom <= 12] { marker-width: 11; }
  [zoom > 12][zoom <= 14] { marker-width: 16; }
  [zoom > 14]             { marker-width: 20; }
}
