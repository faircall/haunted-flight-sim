#version 330
in vec3 vertexPosition;
in vec2 vertexTexCoord;
in vec3 vertexNormal;
uniform mat4 mvp;
uniform vec2 camera;
uniform vec2 player;
uniform vec2 wind;
uniform float elapsed;
uniform float shadow;
out vec2 fragTexCoord;
out float shade;
out vec2 groundPixel;
void main(){
 vec2 root=vertexNormal.xy;
 float tip=vertexNormal.z;
 vec2 away=root-player;
 float touch=1.0-smoothstep(3.0,20.0,length(away));
 float phase=root.x*.137+root.y*.213;
 float gust=(sin(elapsed*1.8+phase)+.4*sin(elapsed*2.7-phase))*.38;
 float sway=wind.x*.09+gust*min(1.5,length(wind)/9.0);
 vec2 point=vertexPosition.xy;
 point.x+=tip*tip*(sway+touch*sign(away.x)*3.0);
 point.y+=tip*touch*3.0;
 if(shadow>.5){
  vec2 local=point-root;
  point=root+vec2(local.x-local.y*.5,-local.y*.17+1.0);
 }
 gl_Position=mvp*vec4(point-camera,0.0,1.0);
 groundPixel=point;
 fragTexCoord=vertexTexCoord;
 shade=shadow;
}
