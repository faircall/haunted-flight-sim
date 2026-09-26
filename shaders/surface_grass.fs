#version 330
in vec2 fragTexCoord;
in float shade;
uniform sampler2D texture0;
uniform sampler2D blockerTexture;
uniform vec2 worldSize;
in vec2 groundPixel;
out vec4 finalColor;
void main(){
 if(texture(blockerTexture,(floor(groundPixel)+.5)/worldSize).r>.5)discard;
 vec4 color=texture(texture0,fragTexCoord);
 if(color.a<.01)discard;
 finalColor=shade>.5?vec4(.14,.12,.065,color.a*.16):color;
}
