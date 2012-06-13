Map {
  background-color: #b8dee6;
}

#countries {
  ::outline {
    line-color: #85c5d3;
    line-width: 2;
    line-join: round;
  }
  polygon-fill: #fff;
}



#invasivespeciesaquat {
  marker-width:6;
  marker-fill:white;
  marker-line-color: darken(white, 50%);
  marker-allow-overlap:true;
}

#invasivespeciesaquat[COM_NAME = "purple loosestrife"] {
  marker-fill:purple;
  marker-line-color: darken(purple, 50%);
}

#invasivespeciesaquat[COM_NAME = "zebra mussel"] {
  marker-fill:grey;
  marker-line-color: darken(grey, 50%);
}

#invasivespeciesaquat[COM_NAME = "curly-leaf pondweed"] {
  marker-fill:green;
  marker-line-color: darken(green, 50%);
}

#invasivespeciesaquat[COM_NAME = "goldfish"] {
  marker-fill:yellow;
  marker-line-color: darken(yellow, 50%);
}


#20120613minnesotasta {
  line-color:#594;
  line-width:0.5;
  polygon-opacity:1;
  polygon-fill:#ae8;
}
