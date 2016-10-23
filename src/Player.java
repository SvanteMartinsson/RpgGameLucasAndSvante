
public class Player extends GameObject{

	String klass;
	String weapon;
	int armor = 0;
	int invSpot;
	int lastSpot = 0;
	int xpReq = 100;
	int gold = 0;
	int xp = 0;
	

	public Player(int hp, int dmg, String name, String klass){
		this.hp = hp;
		this.dmg = dmg;
		this.name = name;
		this.klass = klass;

		if(klass.equals("tank")){
			maxHp = 120;
		}else if(klass.equals("fighter")){
			maxHp = 100;
		}
		
		hp = maxHp;
		
	}
	
	public void levelUp(){
		if(xp == xpReq){
			lvl++;
			xp = 0;
			xpReq *= xpReq*1.5;
		}
	}
	
	
	public void displayStats(){
		System.out.println(dmg + " DMG");
		System.out.println(hp + " HP");
		System.out.println(armor + " ARMOR");
	}
	

}
