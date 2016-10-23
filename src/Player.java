
public class Player extends GameObject{

	String weapon;
	int armor = 0;
	int invSpot;
	int lastSpot = 0;
	
	int gold = 0;
	int xp = 0;
	String klass;

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
		dodgeChance = 4;
		
	}

	
	// Gör en level upgrade klass
	
	public void attack() {
		
		
	}
	
	public void displayStats(){
		System.out.println(dmg + " DMG");
		System.out.println(hp + " HP");
		System.out.println(armor + " ARMOR");
	}
	

}
