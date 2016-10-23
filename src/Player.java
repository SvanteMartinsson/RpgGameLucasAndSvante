
public class Player extends GameObject{

	String[] inv = new String[3];
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
		
	}
	// Gör en level upgrade klass
	
	public void addToInv(String item){
		inv[lastSpot] = item;
		lastSpot++;
	}
	
	public void deleteFromInv(){
		inv[lastSpot] = " ";
	}
	
	public void displayStats(){
		System.out.println(dmg + " DMG");
		System.out.println(hp + " HP");
	}
	
	public void checkForItems(){
		for(int i = 0; i<lastSpot; i++){
			
			if(inv[i] == "knife"){
				dmg+=5;
				
			}
		}
	}
	
	public void displayInv(){
		
		// Displays the inventory with place number
		for(int i = 0; i<lastSpot; i++){
			invSpot = i+1;
			System.out.println(i+1 + " " + inv[i]);
		}
	}

}
