import java.util.Scanner;

public class Player extends GameObject{

	String klass;
	int armor = 0;
	int invSpot;
	int lastSpot = 0;
	int xpReq = 100;
	int xpLeft;
	
	int weaponId;
	
	String[] weaponArray = new String[4];
	
	int inputVar;
	
	boolean loop = true;
	
	Scanner scanner = new Scanner(System.in);


	public Player(int hp, int dmg, String name, String klass){
		this.hp = hp;
		this.dmg = dmg;
		this.name = name;
		this.klass = klass;
		gold = 0;

		xp = 0;

		if(klass.equals("tank")){
			maxHp = 120;
		}else if(klass.equals("fighter")){
			maxHp = 100;
		}

		hp = maxHp;

	}
	
	public void initWeaponArray(){
		weaponArray[0] = "Knife";
		weaponArray[1] = "Sword";
		weaponArray[2] = "Axe";
		weaponArray[3] = "Longsword";
	}

	public void incStats(){
		
		System.out.println("You just increased lvl! Type '1' for increased dmg and '2' for increased hp! ");
		
		while(loop){
		inputVar = scanner.nextInt();
		if(inputVar == 1){
			dmg += 5;
			System.out.println("Damage increased! New damage: " + dmg);
			loop = false;
		}else if(inputVar == 2){
			hp += 10;
			System.out.println("Health increased! New health: " + hp);
			loop = false;
		}else{
			System.out.println("Wrong input!");
		}
		}
	}

	public void levelUp(){
		if(xp >= xpReq){
			xp = 0;
			xpReq *= xpReq*1.00000000000;
			incStats();
			lvl++;
		}
	}

	public void update(){
		
		levelUp();
	}


	
	public void displayInv(){
		System.out.println("Inventory");
		System.out.println("-------------------");
		System.out.println(gold + " Gold");
		System.out.println("You have a " + weaponArray[weaponId] + " as a weapon");
		System.out.println("-------------------");
		System.out.println();
		
	}
	
	public void displayStats(){
		xpLeft = xpReq - xp;
		System.out.println(dmg + " DMG");
		System.out.println(hp + " HP");
		System.out.println(armor + " ARMOR");
		System.out.println(xp + " XP, " + xpLeft + " XP left to next level");
	}


}
