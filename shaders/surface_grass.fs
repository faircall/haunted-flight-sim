#version 330
in vec2 fragTexCoord;
in float shade;
uniform sampler2D texture0;
out vec4 finalColor;
void main(){
 vec4 color=texture(texture0,fragTexCoord);
 if(color.a<.01)discard;
 finalColor=shade>.5?vec4(.14,.12,.065,color.a*.16):color;
}
