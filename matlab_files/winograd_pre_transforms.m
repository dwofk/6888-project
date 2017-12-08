%% Ifmap Pre Transformations
% Reference matrix transforms
B_T = [1,0,-1,0;0,1,1,0;0,-1,1,0;0,1,0,-1]
B = transpose(B_T)

D00 = 1;
D01 = 20;
D02 = 3;
D03 = 4;
D10 = 5;
D11 = 6;
D12 = 17;
D13 = 8;
D20 = 9;
D21 = 3;
D22 = 11;
D23 = 12;
D30 = 13;
D31 = 22;
D32 = 15;
D33 = 16;
%syms D00 D01 D02 D03 D10 D11 D12 D13 D20 D21 D22 D23 D30 D31 D32 D33
d = [D00 D01 D02 D03; D10 D11 D12 D13; D20 D21 D22 D23; D30 D31 D32 D33]
d = d*128; % left shift by 128
v = B_T*d*B

v00 = (D00 - D02 - D20 + D22)*128;
v01 = (D01 + D02 - D21 - D22)*128;
v02 = (D02 - D01 + D21 - D22)*128;
v03 = (D01 - D03 - D21 + D23)*128;
v10 = (D10 - D12 + D20 - D22)*128;
v11 = (D11 + D12 + D21 + D22)*128;
v12 = (D12 - D11 - D21 + D22)*128;
v13 = (D11 - D13 + D21 - D23)*128;
v20 = (D12 - D10 + D20 - D22)*128;
v21 = (D21 - D12 - D11 + D22)*128;
v22 = (D11 - D12 - D21 + D22)*128;
v23 = (D13 - D11 + D21 - D23)*128;
v30 = (D10 - D12 - D30 + D32)*128;
v31 = (D11 + D12 - D31 - D32)*128;
v32 = (D12 - D11 + D31 - D32)*128;
v33 = (D11 - D13 - D31 + D33)*128;

v_hard = [v00 v01 v02 v03; v10 v11 v12 v13; v20 v21 v22 v23; v30 v31 v32 v33]

%% Weight Pre Transformations
% Reference matrix transformations
G = [1,0,0;0.5,0.5,0.5;0.5,-0.5,0.5;0,0,1]
G_T = transpose(G)

G00 = 1;
G01 = 2;
G02 = 3;
G10 = 4;
G11 = 5;
G12 = 6;
G20 = 7;
G21 = 8;
G22 = 9;

%syms G00 G01 G02 G10 G11 G12 G20 G21 G22

g = [G00 G01 G02; G10 G11 G12; G20 G21 G22]
g = g*128;
u = G*g*G_T

% weight transformations: adds and bit shifts
u00 = (G00)*128;
u01 = (G00 + G01 + G02)*64;
u02 = (G00 - G01 + G02)*64;
u03 = (G02)*128;
u10 = (G00 + G10 + G20)*64;
u11 = (G00 + G01 + G02 + G10 + G11 + G12 + G20 + G21 + G22)*32;
u12 = (G00 - G01 + G02 + G10 - G11 + G12 + G20 - G21 + G22)*32;
u13 = (G02 + G12 + G22)*64;
u20 = (G00 - G10 + G20)*64;
u21 = (G00 + G01 + G02 - G10 - G11 - G12 + G20 + G21 + G22)*32;
u22 = (G00 - G01 + G02 - G10 + G11 - G12 + G20 - G21 + G22)*32;
u23 = (G02 - G12 + G22)*64;
u30 = (G20)*128;
u31 = (G20 + G21 + G22)*64;
u32 = (G20 - G21 + G22)*64;
u33 = (G22)*128;

u_hard = [u00 u01 u02 u03; u10 u11 u12 u13; u20 u21 u22 u23; u30 u31 u32 u33]
